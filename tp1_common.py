"""TP 01 - Operation Ghost Bus: shared tools (given to you, do not modify).

Standard library only (Python 3.8+). Nothing to install.
This file contains the bus simulator, the mission checker and the log reader.
"""
import csv
import hashlib
import os


# ------------------------------------------------------------------ messages
# The five messages of the Zephyr prototype (same as in the lecture).
# period is in seconds, dlc is the number of data bytes.
MESSAGES = [
    dict(name="Engine speed", id=0x100, period=0.010, dlc=8),
    dict(name="Braking",      id=0x200, period=0.020, dlc=4),
    dict(name="Temperature",  id=0x300, period=0.100, dlc=2),
    dict(name="Dashboard",    id=0x400, period=0.050, dlc=8),
    dict(name="Diagnostics",  id=0x500, period=0.100, dlc=8),
]


def _frame_bits_with_ifs(dlc):
    """Bits on the bus for one standard data frame, without stuff bits,
    including the 3-bit inter-frame space."""
    return 44 + 8 * dlc + 3


# ------------------------------------------------------------------ simulator
def simulate(messages, bit_rate, duration=1.0):
    """Simulate a CAN bus.

    messages : list of dict(name, id, period, dlc)
    bit_rate : bits per second, for example 125_000
    duration : simulated time in seconds

    Rules of the simulation:
      - each message is released periodically (at 0, T, 2T, ...);
      - when the bus is free, the waiting frame with the SMALLEST identifier
        is sent (this is the result of arbitration);
      - a frame that has started is never interrupted.

    Returns (load, stats):
      load  : busy time / duration (can exceed 1.0 if the bus is overloaded)
      stats : {id: {"sent", "max_wait", "total_wait", "late"}}
              waits are in seconds; "late" counts frames whose wait plus
              transmission time exceeded their period.
    """
    tb = 1.0 / bit_rate
    releases = []                              # (release time, id)
    for m in messages:
        k = 0
        while k * m["period"] < duration:
            releases.append((k * m["period"], m["id"]))
            k += 1
    releases.sort()
    by_id = {m["id"]: m for m in messages}
    stats = {m["id"]: {"sent": 0, "max_wait": 0.0, "total_wait": 0.0, "late": 0} for m in messages}
    t, busy, i, queue = 0.0, 0.0, 0, []
    while i < len(releases) or queue:
        while i < len(releases) and releases[i][0] <= t + 1e-12:
            queue.append(releases[i])
            i += 1
        if not queue:                           # bus idle: jump to next release
            t = releases[i][0]
            continue
        queue.sort(key=lambda x: (x[1], x[0]))  # smallest identifier first
        released, ident = queue.pop(0)
        m = by_id[ident]
        tx = _frame_bits_with_ifs(m["dlc"]) * tb
        wait = max(0.0, t - released)
        s = stats[ident]
        s["sent"] += 1
        s["total_wait"] += wait
        s["max_wait"] = max(s["max_wait"], wait)
        if wait + tx > m["period"] + 1e-12:
            s["late"] += 1
        t += tx
        busy += tx
    return busy / duration, stats


def show(title, messages, bit_rate, duration=1.0):
    """Run the simulation and print a readable table."""
    load, st = simulate(messages, bit_rate, duration)
    print("\n== " + title + " ==")
    print("Bus load: {:.2f} %".format(100 * load))
    print("{:<16}{:>7}{:>7}{:>14}{:>14}{:>7}".format("Message", "id", "sent", "max wait", "mean wait", "late"))
    for m in messages:
        s = st[m["id"]]
        mean = s["total_wait"] / s["sent"] if s["sent"] else 0
        print("{:<16}{:>7}{:>7}{:>11.3f} ms{:>11.3f} ms{:>7}".format(
            m["name"], hex(m["id"]), s["sent"], s["max_wait"] * 1e3, mean * 1e3, s["late"]))
    return load, st


# ------------------------------------------------------------------ team and log
_team = None


def set_team(number):
    """Declare your team number (given by the lecturer). Each team has its own
    recording of the bus, so each team has its own intruder to find."""
    global _team
    if not isinstance(number, int) or not 0 <= number <= 30:
        raise ValueError("The team number must be a whole number from 0 to 30.")
    _team = number
    print("Team %d registered." % number)


def load_log(path=None):
    """Read the bus traffic recorded for YOUR team.
    Returns a list of tuples (time_ms, identifier, bytes), in time order."""
    if path is None:
        if _team is None:
            raise RuntimeError("Call set_team(your_number) before load_log().")
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "can_log_team%02d.csv" % _team)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        return [(float(t), int(i, 16), int(d)) for t, i, d in reader]


# ------------------------------------------------------------------ checker
# Only fingerprints (SHA-256 hashes) of the correct answers are stored here,
# so the answers cannot be read from this file.
_HASHES = {
    1: "4a65187f0ebb8735fed2993de041aac9cbadc044f03e462b9a93a1028a779362",
    2: "142a40ed432afac237a18b9e837c05aa7d677a8d0dee675aebbab0780974da74",
    3: "355d207305756be2781f79b76afc3ed70fe132a29df77accc476a5d683b23456",
    4: "0100ee27c6205a72b0e1646e143f9340467d5ce0ab224af88fe19c736e5827fa",
    5: "9f5f548e45db22ed4e797bf33dc0c6428777065da37d604314984f185bee3623",
    6: "e29b287e6a6a35b32851845987ecf8d12ae86a609cb94b97e26b0bf0ac0e22d0",
}
# missions 7 and 8 depend on the team: (fingerprint 7, fingerprint 8)
_TEAM_HASHES = {
    0: ("28bd00d12362779ddc23", "d77280f53bd195e081c1"),
    1: ("d72cfe1bb55a167d39d4", "1e39f4585e069f71eb4a"),
    2: ("4c73e5e01e3b47d8caa1", "1c9bd92e46b1b49cfcdf"),
    3: ("25af520a8ea9b0070a4a", "dfff147218bc82f7528b"),
    4: ("3d2fb2b1347e387d9b0d", "a4bf6320fd1a3f27da87"),
    5: ("e23b4aa18ca51245b028", "67885150466ac18c6243"),
    6: ("5c0776f43e9a33b2e71f", "fe246caf0dd74eb75570"),
    7: ("728b6e442e330417ec5b", "8718ca89a15aa39b5bb9"),
    8: ("1d35fe922e8af948f747", "73412c7cec288ccaf4ff"),
    9: ("0025b29ffd7bd5ce678f", "b7e6a639c4683fc44f90"),
    10: ("06b986fc042446c5a2a0", "09a87641bda986f44bdb"),
    11: ("98337dac70f21cfcc88d", "5826fb1948249a700107"),
    12: ("4c197d8b73e9b5be4e25", "3dfccc51de200c90c87f"),
    13: ("b51edca4629ad9020932", "70e014208ee057398086"),
    14: ("3ccd0cf2da3eb15a7725", "a75ae7d59637b72d6b83"),
    15: ("66167a374f3c97ef5b8e", "f0562da0f7c69f0b7973"),
    16: ("4a9b132c0b2b84f16cfe", "1664042a4f0b1535abd0"),
    17: ("6297a2a9c18b17795806", "528a65b878ef3ac6d325"),
    18: ("8984c6259390aa82b28b", "fb6ec9e707f4c77a3f15"),
    19: ("afd4c37d4a1bb89638ad", "fad5d8d872f43d00f8af"),
    20: ("a63eae2ae4e4ad8d60bc", "ebec09b7442bee3521be"),
    21: ("7d4274d73bc8498b696b", "d9364abb5c61a9b1aba2"),
    22: ("776f2c67582f3ce8e53d", "de4369ae6d6e3d708b0d"),
    23: ("8bb8a60023954bf2f223", "f92c02e016a64ddf84ca"),
    24: ("ae2280b735bcf8600cb5", "5c9c861d43c48b23b25b"),
    25: ("6642a388dfbec7691f04", "62384d293620042c352b"),
    26: ("6c08b5b53c687299a253", "7b5244255ef002c9f1b9"),
    27: ("e779d3dd14bf589eacea", "f7bd2adf8b5e379ed78c"),
    28: ("6a42bdbcb55f2632f73b", "129693ebcd82746235a7"),
    29: ("5b228a6c164a4f651453", "4371a9411afb619debbb"),
    30: ("1b5daf23cb732495e5b9", "dce8dbb8936c7b20666c"),
}
_POINTS = {1: 10, 2: 10, 3: 15, 4: 10, 5: 15, 6: 10, 7: 15, 8: 15}
_TITLES = {1: "Clock the frame", 2: "Stuff it", 3: "Who gets to talk?", 4: "Traffic report",
           5: "Last in line", 6: "The flood", 7: "Unmask the ghost", 8: "Count the ghosts"}
_score = {}


def _canon(x):
    if isinstance(x, str):
        t = x.strip()
        if t.lower().startswith("0x"):          # "0x100" is accepted like 256
            try:
                return "{:.3f}".format(float(int(t, 16)))
            except ValueError:
                return t
        return t
    return "{:.3f}".format(float(x))


def check(mission, answer):
    """check(3, my_answer) tests your answer to mission 3."""
    if mission not in _POINTS:
        print("There is no mission %r. Missions go from 1 to 8." % (mission,))
        return False
    if mission in (7, 8):
        if _team is None:
            print("Missions 7 and 8 depend on your team: call set_team(your_number) first.")
            return False
        h = hashlib.sha256(("ghostbus|team%d|%d|%s" % (_team, mission, _canon(answer))).encode()).hexdigest()[:20]
        ok = h == _TEAM_HASHES[_team][mission - 7]
    else:
        h = hashlib.sha256(("ghostbus|%d|%s" % (mission, _canon(answer))).encode()).hexdigest()
        ok = h == _HASHES[mission]
    if ok:
        first = mission not in _score
        _score[mission] = _POINTS[mission]
        print("MISSION %d COMPLETE: %s%s   Score: %d / 100"
              % (mission, _TITLES[mission], ("  (+%d points)" % _POINTS[mission]) if first else "  (already counted)",
                 sum(_score.values())))
        return True
    print("Mission %d: not yet. Re-read the mission, check your units and your rounding." % mission)
    return False


def score():
    """Print the current score, the rank and the missions already completed."""
    total = sum(_score.values())
    rank = "Bus Master" if total == 100 else "Bus Expert" if total >= 80 else "CAN Engineer" if total >= 50 else "Bus Apprentice"
    done = sorted(_score)
    team = "Team %d   " % _team if _team is not None else ""
    print("%sScore: %d / 100   Rank: %s   Missions completed: %s" % (team, total, rank, done if done else "none yet"))
