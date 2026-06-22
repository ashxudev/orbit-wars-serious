"""Orbit Wars agent.

Engine-exact forward simulation + marginal-value greedy mission planner.

Pipeline each turn:
  1. Predict every planet/comet position for the whole horizon (closed form,
     matching the engine's rotation indexing incl. the step-0 quirk).
  2. Simulate every in-flight fleet (all owners) with the engine's exact
     swept-pair collision test -> landing events (planet, tick, owner, ships).
  3. Build per-planet ownership/garrison timelines from those events.
  4. Generate candidate missions (capture / defend / evacuate / funnel);
     each is priced by the marginal change it causes in projected final
     score differential (my ships - lambda * enemy ships at horizon).
  5. Greedily commit the best missions, updating timelines after each.
"""

import math
import time

LOG1000 = math.log(1000.0)
BOARD = 100.0
CENTER = 50.0
SUN_R = 10.0
ROT_LIM = 50.0
END_STEP = 498          # last step at which score is counted
H_MAX = 110

# tunables
MARGIN_NEUTRAL = 2      # extra ships beyond computed requirement
MARGIN_ENEMY = 4
HOLD_OK_FALLBACK = True
FUNNEL_MIN = 20         # min chunk size for rear->front transfers
FUNNEL_FRac = 0.6
POS_BONUS = 0.10        # value per ship per 100 units of front-distance gained
RESP_DISCOUNT = 0.55    # how strongly enemy counter-reinforcement discounts value
MIN_V = 1.0             # do not commit missions below this marginal value
MAX_MOVES = 16


def fleet_speed(n, max_speed):
    if n <= 1:
        return 1.0
    r = math.log(n) / LOG1000
    if r > 1.0:
        r = 1.0
    return 1.0 + (max_speed - 1.0) * r ** 1.5


def _swept_hit(ax, ay, bx, by, p0x, p0y, p1x, p1y, r):
    """Engine's swept_pair_hit: fleet seg A->B vs planet chord P0->P1 within r."""
    d0x = ax - p0x
    d0y = ay - p0y
    dvx = (bx - ax) - (p1x - p0x)
    dvy = (by - ay) - (p1y - p0y)
    a = dvx * dvx + dvy * dvy
    b = 2.0 * (d0x * dvx + d0y * dvy)
    c = d0x * d0x + d0y * d0y - r * r
    if a < 1e-12:
        return c <= 0.0
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return False
    sq = math.sqrt(disc)
    return (-b + sq) / (2.0 * a) >= 0.0 and (-b - sq) / (2.0 * a) <= 1.0


def _seg_sun_dist(x1, y1, x2, y2):
    """Min distance from sun center to segment."""
    wx = x2 - x1
    wy = y2 - y1
    l2 = wx * wx + wy * wy
    px = CENTER - x1
    py = CENTER - y1
    if l2 == 0.0:
        return math.hypot(px, py)
    t = (px * wx + py * wy) / l2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return math.hypot(px - t * wx, py - t * wy)


def _resolve_combat(owner, ships, arrivals):
    """Engine combat: arrivals = [(owner, n), ...] hitting (owner, ships)."""
    by = {}
    for o, n in arrivals:
        by[o] = by.get(o, 0) + n
    groups = sorted(by.items(), key=lambda kv: kv[1], reverse=True)
    top_o, top_n = groups[0]
    if len(groups) > 1:
        second = groups[1][1]
        surv = top_n - second
        if top_n == second:
            surv = 0
        surv_o = top_o if surv > 0 else -1
    else:
        surv = top_n
        surv_o = top_o
    if surv > 0:
        if owner == surv_o:
            ships += surv
        else:
            ships -= surv
            if ships < 0:
                owner = surv_o
                ships = -ships
    return owner, ships


def think(obs, cfg):
    t_start = time.time()
    step = obs["step"]
    me = obs["player"]
    max_speed = 6.0
    comet_speed = 4.0
    if cfg:
        try:
            max_speed = float(cfg.get("shipSpeed", 6.0) or 6.0)
            comet_speed = float(cfg.get("cometSpeed", 4.0) or 4.0)
        except Exception:
            pass

    remaining = END_STEP - step
    if remaining <= 0:
        return []
    H = min(H_MAX, remaining)

    # FFA: with 3 enemies the full-pessimism response gate (no pinning) is
    # closer to truth — pinning assumes the one defender is also the only
    # threat, which only holds in 1v1. NOTE: initial_planets owners are all
    # -1 (engine snapshots before home assignment) — detect from live state.
    ffa = me >= 2 or any(p[1] >= 2 for p in obs["planets"]) \
        or any(f[1] >= 2 for f in obs["fleets"])

    overage = obs.get("remainingOverageTime", 60) or 60
    budget = 0.72 if overage > 20 else (0.5 if overage > 8 else 0.3)
    deadline = t_start + budget

    planets_raw = obs["planets"]
    fleets_raw = obs["fleets"]
    comet_groups = obs.get("comets") or []
    comet_id_set = set(obs.get("comet_planet_ids") or [])
    w = obs["angular_velocity"]
    initial = {p[0]: p for p in (obs.get("initial_planets") or [])}

    NP = len(planets_raw)
    pid = [0] * NP
    owner = [0] * NP
    pr = [0.0] * NP
    pships = [0] * NP
    pprod = [0] * NP
    is_comet = [False] * NP

    comet_path = {}
    for g in comet_groups:
        pids = g.get("planet_ids", [])
        paths = g.get("paths", [])
        ci = g.get("path_index", 0)
        for slot, cpid in enumerate(pids):
            if slot < len(paths):
                comet_path[cpid] = (paths[slot], ci)

    pos = []            # pos[i][k] = (x, y) for k = 0..H
    dead_from = []      # tick at which comet expires (stays put that tick, gone after)
    mv = []             # max per-tick movement (for quick-reject)
    for i in range(NP):
        p = planets_raw[i]
        pid[i] = p[0]
        owner[i] = p[1]
        x0 = p[2]
        y0 = p[3]
        pr[i] = p[4]
        pships[i] = p[5]
        pprod[i] = p[6]
        if p[0] in comet_path:
            is_comet[i] = True
            path, ci = comet_path[p[0]]
            plen = len(path)
            arr = []
            last = (x0, y0)
            for k in range(H + 1):
                j = ci + k
                if 0 <= j < plen:
                    last = (path[j][0], path[j][1])
                arr.append(last)
            pos.append(arr)
            dead_from.append(max(1, plen - ci))
            mv.append(comet_speed + 0.2)
        else:
            ip = initial.get(p[0])
            rotating = False
            orad = 0.0
            if ip is not None:
                orad_i = math.hypot(ip[2] - CENTER, ip[3] - CENTER)
                rotating = (orad_i + p[4]) < ROT_LIM
            if rotating and w:
                orad = math.hypot(x0 - CENTER, y0 - CENTER)
                a0 = math.atan2(y0 - CENTER, x0 - CENTER)
                arr = []
                for k in range(H + 1):
                    kk = k if step >= 1 else (k - 1 if k > 0 else 0)
                    a = a0 + w * kk
                    arr.append((CENTER + orad * math.cos(a),
                                CENTER + orad * math.sin(a)))
                pos.append(arr)
                mv.append(orad * w + 0.05)
            else:
                pos.append([(x0, y0)] * (H + 1))
                mv.append(0.0)
            dead_from.append(H + 2)
        if pships[i] < 0:
            pships[i] = 0

    rng_np = range(NP)

    def fly(x, y, ang, n, start_k=0):
        """Simulate a fleet; returns (planet_index, tick) on landing,
        (-1, tick) if destroyed, (-2, H+1) if it outlives the horizon.
        start_k > 0 simulates a launch that many ticks in the future
        (orbits are deterministic, so the check is exact)."""
        sp = fleet_speed(n, max_speed)
        dx = math.cos(ang) * sp
        dy = math.sin(ang) * sp
        for k in range(start_k + 1, H + 1):
            nx = x + dx
            ny = y + dy
            for i in rng_np:
                if k > dead_from[i]:
                    continue
                ox, oy = pos[i][k - 1]
                ddx = ox - x
                ddy = oy - y
                lim = sp + mv[i] + pr[i] + 0.7
                if ddx * ddx + ddy * ddy > lim * lim:
                    continue
                qx, qy = pos[i][k]
                if _swept_hit(x, y, nx, ny, ox, oy, qx, qy, pr[i]):
                    return (i, k)
            if nx < 0.0 or nx > BOARD or ny < 0.0 or ny > BOARD:
                return (-1, k)
            if _seg_sun_dist(x, y, nx, ny) < SUN_R:
                return (-1, k)
            x = nx
            y = ny
        return (-2, H + 1)

    # ---- landing events from all in-flight fleets ----
    events = [dict() for _ in rng_np]
    for f in fleets_raw:
        land, k = fly(f[2], f[3], f[4], f[6])
        if land >= 0 and k < dead_from[land]:
            events[land].setdefault(k, []).append((f[1], f[6]))

    # ---- per-planet timeline simulation ----
    def sim(i, mods=None, ships0=None):
        """Returns (owner_at_H, ships_at_H, first_lost_tick, first_gain_tick).
        owner -9 means the comet expired (everything lost)."""
        ow = owner[i]
        s = pships[i] if ships0 is None else ships0
        evs = events[i]
        df = dead_from[i]
        prod = pprod[i]
        first_lost = None
        first_gain = None
        was_me = ow == me
        for k in range(1, H + 1):
            if k >= df:
                return (-9, 0, first_lost, first_gain)
            if ow != -1:
                s += prod
            arr = evs.get(k)
            m = mods.get(k) if mods else None
            if arr or m:
                lst = (list(arr) if arr else [])
                if m:
                    lst.extend(m)
                ow2, s = _resolve_combat(ow, s, lst)
                if ow2 != ow:
                    if ow2 == me and first_gain is None:
                        first_gain = k
                    if ow == me and first_lost is None:
                        first_lost = k
                    ow = ow2
        return (ow, s, first_lost, first_gain)

    enemies = set()
    for i in rng_np:
        if owner[i] != -1 and owner[i] != me:
            enemies.add(owner[i])
    for f in fleets_raw:
        if f[1] != me:
            enemies.add(f[1])
    lam = 1.0 if len(enemies) <= 1 else 0.55

    # per-opponent denial weight: hurting the strongest enemy matters most,
    # a dying enemy's holdings are barely worth denying (but still cheap to take)
    enemy_strength = {}
    for i in rng_np:
        if owner[i] != -1 and owner[i] != me:
            enemy_strength[owner[i]] = enemy_strength.get(owner[i], 0) + pships[i] + pprod[i] * 25
    for f in fleets_raw:
        if f[1] != me:
            enemy_strength[f[1]] = enemy_strength.get(f[1], 0) + f[6]
    max_str = max(enemy_strength.values()) if enemy_strength else 1
    lam_by = {}
    for o, s in enemy_strength.items():
        lam_by[o] = lam * (0.25 + 0.75 * s / max_str) if len(enemies) > 1 else lam

    tail = remaining - H  # production turns beyond the horizon

    def tl_value(i, ow_H, s_H):
        if ow_H == -9 or ow_H == -1:
            return 0.0
        extra = 0 if is_comet[i] else pprod[i] * tail
        if ow_H == me:
            return s_H + extra
        return -lam_by.get(ow_H, lam) * (s_H + extra)

    base_tl = [sim(i) for i in rng_np]
    base_val = [tl_value(i, base_tl[i][0], base_tl[i][1]) for i in rng_np]

    # full per-tick (owner, ships) tracks for pre-ranking against the
    # *future* state at arrival (catches snipe windows the current state hides)
    def track(i):
        ow = owner[i]
        s = pships[i]
        evs = events[i]
        df = dead_from[i]
        prod = pprod[i]
        ows = [ow] * (H + 1)
        shs = [s] * (H + 1)
        for k in range(1, H + 1):
            if k >= df:
                for j in range(k, H + 1):
                    ows[j] = -9
                    shs[j] = 0
                break
            if ow != -1:
                s += prod
            arr = evs.get(k)
            if arr:
                ow, s = _resolve_combat(ow, s, list(arr))
            ows[k] = ow
            shs[k] = s
        return ows, shs

    base_track = [track(i) for i in rng_np]

    cur_ships = list(pships)   # mutated as missions are committed

    my_idx = [i for i in rng_np if owner[i] == me]
    enemy_idx = [i for i in rng_np if owner[i] != me and owner[i] != -1]

    if not my_idx:
        return []

    # distance helper on current positions
    def d0(i, j):
        ax, ay = pos[i][0]
        bx, by = pos[j][0]
        return math.hypot(ax - bx, ay - by)

    # front distance: distance to nearest enemy planet (for funneling)
    def front_dist(i):
        best = 200.0
        for e in enemy_idx:
            d = d0(i, e)
            if d < best:
                best = d
        return best

    def aim_and_validate(si, ti, n):
        """Find launch angle hitting ti with n ships. Returns (angle, tick) or None."""
        sx, sy = pos[si][0]
        sp = fleet_speed(n, max_speed)
        tx0, ty0 = pos[ti][0]
        T = max(1.0, (math.hypot(tx0 - sx, ty0 - sy) - pr[ti] - pr[si]) / sp)
        a = 0.0
        for _ in range(3):
            Tc = int(T + 0.5)
            if Tc < 1:
                Tc = 1
            if Tc > H:
                Tc = H
            if Tc >= dead_from[ti]:
                Tc = dead_from[ti] - 1
                if Tc < 1:
                    return None
            tx, ty = pos[ti][Tc]
            a = math.atan2(ty - sy, tx - sx)
            T = max(1.0, (math.hypot(tx - sx, ty - sy) - pr[ti] - pr[si]) / sp)
        for da in (0.0, 0.04, -0.04, 0.10, -0.10):
            ang = a + da
            lx = sx + math.cos(ang) * (pr[si] + 0.101)
            ly = sy + math.sin(ang) * (pr[si] + 0.101)
            land, k = fly(lx, ly, ang, n)
            if land == ti and k < dead_from[ti]:
                return (ang, k)
        return None

    def needed_for(ti, T, cap, want_hold):
        """Minimal n arriving at T that ends with the planet mine (binary search).
        If want_hold fails entirely, fall back to capture-at-T."""
        def ok_hold(n):
            ow, s, fl, fg = sim(ti, {T: [(me, n)]})
            return ow == me
        if ok_hold(cap):
            lo, hi = 1, cap
            while lo < hi:
                mid = (lo + hi) // 2
                if ok_hold(mid):
                    hi = mid
                else:
                    lo = mid + 1
            return lo
        if not want_hold or not HOLD_OK_FALLBACK:
            return None
        def ok_cap(n):
            ow, s, fl, fg = sim(ti, {T: [(me, n)]})
            return fg is not None and fg <= T
        if not ok_cap(cap):
            return None
        lo, hi = 1, cap
        while lo < hi:
            mid = (lo + hi) // 2
            if ok_cap(mid):
                hi = mid
            else:
                lo = mid + 1
        return lo

    def enemy_response(ti, T):
        """Enemy ships that could plausibly reach ti before/around T."""
        tot = 0
        for e in enemy_idx:
            if e == ti:
                continue
            eta = d0(e, ti) / 4.5
            if eta <= T + 2:
                tot += cur_ships[e]
        return tot

    src_val_cache = {}

    def src_value(si, ships0):
        key = (si, ships0)
        v = src_val_cache.get(key)
        if v is None:
            ow, s, fl, fg = sim(si, None, ships0=ships0)
            v = tl_value(si, ow, s)
            src_val_cache[key] = v
        return v

    def eval_mission(si, ti, n_hint=None, funnel=False):
        """Fully price a mission. Returns (V, n, angle, T) or None."""
        avail = cur_ships[si]
        if avail <= 0:
            return None
        contested = False
        race_blocked = False
        if funnel:
            n = n_hint
            av = aim_and_validate(si, ti, n)
            if av is None:
                return None
            ang, T = av
        else:
            # initial guess for sizing
            guess = pships[ti] + 8
            if owner[ti] != -1 and owner[ti] != me:
                guess += pprod[ti] * 15
            if guess > avail:
                guess = avail
            if guess < 1:
                guess = 1
            av = aim_and_validate(si, ti, guess)
            if av is None and guess * 2 <= avail:
                # a bigger fleet is faster: different sweep timing can
                # thread lanes that kill a slow fleet
                guess = guess * 2
                av = aim_and_validate(si, ti, guess)
            if av is None:
                eval_mission.rej = "aim"
                return None
            ang, T = av
            need = needed_for(ti, T, avail, want_hold=True)
            if need is None:
                return None
            if owner[ti] != -1 and owner[ti] != me:
                # hard gate: an attack the defender can answer is a pure ship
                # donation (ledger: 40-53% of production bled in lost attacks).
                # Require beating garrison + everything they can deliver by T.
                resp_full = 0
                for e in enemy_idx:
                    if e == ti:
                        continue
                    force = cur_ships[e] - 5
                    if force <= 0:
                        continue
                    # pinning: a defender planet under threat from my nearby
                    # garrisons can't strip itself to help — subtract the
                    # largest single threat I project onto it
                    pin = 0
                    for m_i in (() if ffa else my_idx):
                        if m_i == si:
                            continue
                        if d0(m_i, e) / 4.5 <= T + 4:
                            t_force = cur_ships[m_i] - 5
                            if t_force > pin:
                                pin = t_force
                    force -= int(0.8 * min(pin, force))
                    if force <= 0:
                        continue
                    sp_e = fleet_speed(force, max_speed)
                    eta_e = 1 + (d0(e, ti) - pr[ti] - pr[e]) / sp_e
                    if eta_e <= T:
                        resp_full += force
                need += resp_full
                if need > avail:
                    return None
            margin = MARGIN_ENEMY if owner[ti] != -1 and owner[ti] != me else MARGIN_NEUTRAL
            race_blocked = False
            if owner[ti] == -1:
                # race-awareness: an equidistant enemy can launch the same
                # turn we do (invisible to the forecast). Same-tick equal
                # arrivals tie and BOTH die (engine rule) — require beating
                # garrison + their plausible racing fleet, else look away.
                e_eta = 1e9
                e_force = 0
                for e in enemy_idx:
                    force = cur_ships[e] - 3
                    if force <= 0:
                        continue
                    sp_e = fleet_speed(force, max_speed)
                    eta_e = 1 + (d0(e, ti) - pr[ti] - pr[e]) / sp_e
                    if eta_e < e_eta:
                        e_eta = eta_e
                        e_force = force
                if e_eta <= T + 1:
                    n_race = need + margin + min(e_force, need + margin)
                    if n_race <= avail:
                        margin += n_race - (need + margin)
                    else:
                        race_blocked = True
            n = need + margin
            # hold-aware sizing: a fresh capture with a tiny garrison is free
            # food for counter-snipes; send enough to survive the plausible
            # counter, or mark the mission contested (value discounted below)
            contested = False
            snipe_req = 0
            for e in enemy_idx:
                eta_e = d0(e, ti) / 4.5
                if eta_e > T + 14:
                    continue
                arr_k = (T + 1) if eta_e <= T else int(eta_e) + 1
                force = cur_ships[e]
                if force > 45:
                    force = 45
                req = need + force - pprod[ti] * (arr_k - T) + 1
                if req > snipe_req:
                    snipe_req = req
            if snipe_req > n:
                if snipe_req <= avail:
                    n = snipe_req
                else:
                    contested = True
            if n > avail:
                n = avail
                if n < need:
                    return None
            # re-aim with the final size (speed changed)
            av = aim_and_validate(si, ti, n)
            if av is None:
                return None
            ang, T2 = av
            if T2 != T:
                need2 = needed_for(ti, T2, avail, want_hold=True)
                if need2 is None:
                    return None
                if need2 + margin > n:
                    n = min(avail, need2 + margin)
                    if n < need2:
                        return None
                    av = aim_and_validate(si, ti, n)
                    if av is None:
                        return None
                    ang, T2 = av
                T = T2
        ow2, s2, fl2, fg2 = sim(ti, {T: [(me, n)]})
        dV_t = tl_value(ti, ow2, s2) - cur_tgt_val[ti]
        dV_s = src_value(si, cur_ships[si] - n) - src_value(si, cur_ships[si])
        V = dV_t + dV_s - 0.05 * T
        if funnel:
            gain = front_dist(si) - front_dist(ti)
            V += POS_BONUS * n * gain / 100.0 * 10.0
        elif owner[ti] != me:
            if race_blocked and V > 0:
                V *= 0.3
            if owner[ti] != -1 and V > 0 and opportunism and not ffa:
                # elites cluster strikes <=5 ticks after the opponent
                # commits a big fleet (70% vs 57% baseline); in FFA the
                # third party punishes the opportunist, so 1v1 only
                V *= 1.3
            if contested and V > 0:
                V *= 0.4
            resp = enemy_response(ti, T)
            if resp > 0:
                # 1v1: a neutral is a race, not a defended position -> light
                # discount. FFA: neutrals genuinely contested by 3 rivals.
                if owner[ti] == -1 and len(enemies) <= 1:
                    w_resp = 0.15
                else:
                    w_resp = RESP_DISCOUNT
                V -= w_resp * min(resp, n)
        return (V, n, ang, T)

    # opportunism: a large enemy fleet just launched (still near source)?
    opportunism = False
    id2i = {pid[i]: i for i in rng_np}
    for f in fleets_raw:
        if f[1] == me or f[6] < 80:
            continue
        srci = id2i.get(f[5])
        if srci is None:
            continue
        sxp, syp = pos[srci][0]
        age = math.hypot(f[2] - sxp, f[3] - syp) / fleet_speed(f[6], max_speed)
        if age <= 5.0:
            opportunism = True
            break

    # current target values (updated after commits)
    cur_tgt_val = list(base_val)

    # ---- candidate pair selection (crude pre-ranking) ----
    pairs = []   # (priority, si, ti, kind)
    for si in my_idx:
        if cur_ships[si] <= 0:
            continue
        scored = []
        for ti in rng_np:
            if ti == si:
                continue
            d = d0(si, ti)
            eta = d / 4.5
            if owner[ti] == me:
                if base_tl[ti][2] is not None:
                    scored.append((4000 - d, ti))   # defend falling friend
                continue
            if eta >= remaining - 4:
                continue
            if is_comet[ti]:
                if dead_from[ti] < eta + 6 or pships[ti] > 15:
                    continue
            # rank against the forecast state at estimated arrival, not now
            ka = int(eta)
            if ka > H:
                ka = H
            fo = base_track[ti][0][ka]
            fs = base_track[ti][1][ka]
            if fo == -9 or fo == me:
                continue
            denial = 1.0 + (lam_by.get(fo, lam) if fo != -1 else 0.0)
            cost = fs + (pprod[ti] * eta * 0.5 if fo != -1 else 0)
            crude = pprod[ti] * (remaining - eta) * denial - cost - 0.8 * d
            # per-seat tie-break: identical agents otherwise race the same
            # neutral every turn and same-tick ties kill both fleets forever
            crude += ((pid[ti] * 7919 + me * 104729) % 13) * 0.03
            if crude > 0:
                scored.append((crude, ti))
        scored.sort(reverse=True)
        for crude, ti in scored[:12]:
            pairs.append((crude, si, ti, "attack"))

    # evacuation candidates: my planets about to fall, comets about to expire
    safe_my = [i for i in my_idx if base_tl[i][2] is None and not is_comet[i]]
    for si in my_idx:
        doomed = base_tl[si][2] is not None and base_tl[si][2] <= 3
        comet_exp = is_comet[si] and dead_from[si] <= 14
        if not (doomed or comet_exp):
            continue
        if cur_ships[si] <= 0:
            continue
        targets = sorted(safe_my, key=lambda j: d0(si, j))[:2] if safe_my else []
        for ti in targets:
            pairs.append((5000.0, si, ti, "evac"))

    pairs.sort(reverse=True)

    relay_budget = [12]

    def try_relay(si, ti, crude):
        """Two-hop route to an unreachable target. Commits only hop 1
        (ships to an own stepping-stone); later turns re-plan hop 2.
        Returns a candidate row or None."""
        d_direct = d0(si, ti)
        best = None
        for R in my_idx:
            if R == si or R == ti or is_comet[R]:
                continue
            if base_tl[R][2] is not None:
                continue
            d1 = d0(si, R)
            d2 = d0(R, ti)
            if d1 < 6 or d1 + d2 > 1.7 * d_direct + 10:
                continue
            if best is None or d1 + d2 < best[1]:
                best = (R, d1 + d2, d2)
        if best is None:
            return None
        R, d_tot, d2 = best
        # size for the target's forecast state at total ETA
        eta_tot = d_tot / 4.0 + 3
        ka = min(H, int(eta_tot))
        fo = base_track[ti][0][ka]
        fs = base_track[ti][1][ka]
        if fo == me or fo == -9:
            return None
        need_rough = fs + (pprod[ti] * 8 if fo != -1 else 0) + MARGIN_NEUTRAL + 3
        n = min(cur_ships[si], need_rough + 4)
        if n < need_rough or n <= 0:
            return None
        av1 = aim_and_validate(si, R, n)
        if av1 is None:
            return None
        ang1, T1 = av1
        if T1 + d2 / 3.5 > H - 2:
            return None
        # verify hop 2 is actually flyable when the ships arrive at R
        rx, ry = pos[R][min(T1, H)]
        sp2 = fleet_speed(n, max_speed)
        T2 = max(1.0, (d2 - pr[ti] - pr[R]) / sp2)
        hop2_ok = False
        for _ in range(3):
            kc = min(H, T1 + int(T2 + 0.5))
            if kc >= dead_from[ti]:
                break
            tx, ty = pos[ti][kc]
            a2 = math.atan2(ty - ry, tx - rx)
            lx = rx + math.cos(a2) * (pr[R] + 0.101)
            ly = ry + math.sin(a2) * (pr[R] + 0.101)
            land2, k2 = fly(lx, ly, a2, n, start_k=T1)
            if land2 == ti and k2 < dead_from[ti]:
                hop2_ok = True
                T_tot = k2
                break
            T2 += 2
        if not hop2_ok:
            return None
        # price as a delayed capture, discounted for re-plan uncertainty
        ow2, s2, fl2, fg2 = sim(ti, {T_tot: [(me, n)]})
        dV_t = tl_value(ti, ow2, s2) - cur_tgt_val[ti]
        dV_s = src_value(si, cur_ships[si] - n) - src_value(si, cur_ships[si])
        V = (dV_t * 0.75) + dV_s - 0.05 * T_tot
        if V < MIN_V:
            return None
        return [V, si, R, n, ang1, T1, "relay"]

    # ---- full evaluation of top candidates ----
    cands = []
    for crude, si, ti, kind in pairs[:90]:
        if time.time() > deadline:
            break
        if kind == "evac":
            n = cur_ships[si]
            if n <= 0:
                continue
            av = aim_and_validate(si, ti, n)
            if av is None:
                continue
            ang, T = av
            # value: ships rescued (they'd die otherwise)
            ow2, s2, _, _ = sim(ti, {T: [(me, n)]})
            dV_t = tl_value(ti, ow2, s2) - cur_tgt_val[ti]
            dV_s = src_value(si, 0) - src_value(si, n)
            V = dV_t + dV_s
            if is_comet[si]:
                V += n * 0.5    # urgency bonus: comet expiry is a hard loss
            cands.append([V, si, ti, n, ang, T, kind])
        else:
            eval_mission.rej = None
            r = eval_mission(si, ti)
            if r is not None:
                V, n, ang, T = r
                cands.append([V, si, ti, n, ang, T, kind])
            elif eval_mission.rej == "aim" and relay_budget[0] > 0:
                # no direct line (sun / sweeping orbiters): relay through an
                # own stepping-stone planet; hop 2 is verified at its actual
                # future launch tick, which is exact for deterministic orbits
                relay_budget[0] -= 1
                rc = try_relay(si, ti, crude)
                if rc is not None:
                    cands.append(rc)

    # funnel candidates: big garrisons far from the front shuttle forward
    if remaining > 60 and len(safe_my) >= 2:
        fronts = sorted(safe_my, key=front_dist)
        front_set = fronts[:max(1, len(fronts) // 3)]
        for si in safe_my:
            if si in front_set or cur_ships[si] < FUNNEL_MIN * 2:
                continue
            n = int(cur_ships[si] * FUNNEL_FRac)
            if n < FUNNEL_MIN:
                continue
            best_t = None
            best_d = 1e9
            for ti in front_set:
                d = d0(si, ti)
                if d < best_d:
                    best_d = d
                    best_t = ti
            if best_t is None:
                continue
            r = eval_mission(si, best_t, n_hint=n, funnel=True)
            if r is not None:
                V, n2, ang, T = r
                cands.append([V, si, best_t, n2, ang, T, "funnel"])

    # ---- greedy commit loop ----
    moves = []
    committed_ship_count = {}
    for _round in range(MAX_MOVES):
        if not cands or time.time() > deadline:
            break
        cands.sort(key=lambda c: c[0], reverse=True)
        best = cands[0]
        V, si, ti, n, ang, T, kind = best
        if V < MIN_V:
            break
        # re-verify against current (post-commit) state
        if n > cur_ships[si]:
            if kind in ("funnel", "relay") and cur_ships[si] >= 10:
                n = cur_ships[si]
                best[3] = n
            else:
                cands.pop(0)
                continue
        if kind not in ("evac", "funnel", "relay"):
            r = eval_mission(si, ti)
            if r is None:
                cands.pop(0)
                continue
            V2, n2, ang2, T2 = r
            if V2 < MIN_V:
                cands.pop(0)
                continue
            if V2 < V - 1e-9:
                best[0] = V2
                best[3] = n2
                best[4] = ang2
                best[5] = T2
                continue   # re-sort and reconsider
            n, ang, T = n2, ang2, T2
        # commit
        moves.append([pid[si], float(ang), int(n)])
        committed_ship_count[si] = committed_ship_count.get(si, 0) + n
        cur_ships[si] -= n
        events[ti].setdefault(T, []).append((me, n))
        ow2, s2, fl2, fg2 = sim(ti)
        cur_tgt_val[ti] = tl_value(ti, ow2, s2)
        src_val_cache.clear()
        cands.pop(0)
        # drop other candidates aimed at the same target (will be re-derived next turn)
        cands = [c for c in cands if c[2] != ti or c[6] == "evac"]

    # final dump: doomed planets / expiring comets send any leftovers
    for si in my_idx:
        left = cur_ships[si]
        if left <= 0:
            continue
        doomed = base_tl[si][2] is not None and base_tl[si][2] <= 2
        comet_exp = is_comet[si] and dead_from[si] <= 3
        if not (doomed or comet_exp):
            continue
        for ti in sorted(safe_my, key=lambda j: d0(si, j))[:3]:
            if ti == si:
                continue
            av = aim_and_validate(si, ti, left)
            if av is not None:
                moves.append([pid[si], float(av[0]), int(left)])
                cur_ships[si] = 0
                break

    return moves


def agent(obs, config=None):
    try:
        return think(obs, config)
    except Exception:
        return []
