"""Build the sample trips DISP-101 to DISP-120 in data/.

Run from the repo root (any Python that has the backend's requirements):

    python scripts/build_sample_trips.py

Each trip is a full case file (profiles, GPS trail, chat, app events, fare) in the same shape as
data/DISP-002.json. The facts are generated from a few parameters, then every case is run through
the real evidence tools and outcome formulas and the script stops if the result is not the one the
trip was designed for. The designed outcomes are written to data/sample_trips.expected.json
(a file the backend and frontend skip, like the other *.expected.json answer keys).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from schemas import DisputeCase  # noqa: E402
from tools.no_show_check import compute_no_show_outcome, no_show_check  # noqa: E402
from tools.route_deviation import _haversine_m, compute_route_deviation_outcome, route_deviation  # noqa: E402
from tools.safety_check import safety_check, safety_override  # noqa: E402

DATA = ROOT / "data"
TZ = "+08:00"

PLACES = {
    "ION Orchard": (1.3040, 103.8318), "Changi Airport T3": (1.3554, 103.9870),
    "Jurong East MRT": (1.3330, 103.7436), "NUS Kent Ridge": (1.2966, 103.7764),
    "Tampines Mall": (1.3525, 103.9453), "Paya Lebar Quarter": (1.3178, 103.8923),
    "Junction 8 Bishan": (1.3507, 103.8485), "Toa Payoh HDB Hub": (1.3326, 103.8474),
    "Woodlands MRT": (1.4370, 103.7865), "Bugis Junction": (1.2993, 103.8559),
    "Marina Bay Sands": (1.2834, 103.8607), "Clementi Mall": (1.3151, 103.7653),
    "HarbourFront Centre": (1.2656, 103.8200), "Waterway Point Punggol": (1.4070, 103.9022),
    "NEX Serangoon": (1.3507, 103.8725), "Novena Square": (1.3203, 103.8438),
    "Chinatown Point": (1.2848, 103.8449), "Leisure Park Kallang": (1.3026, 103.8714),
    "Sentosa Gateway": (1.2547, 103.8199),
}

RIDERS = [
    ("Aisha Rahman", "e-wallet"), ("Daniel Ong", "credit_card"), ("Priya Nair", "e-wallet"),
    ("Jason Lim", "credit_card"), ("Mei Ling Chua", "e-wallet"), ("Ravi Menon", "credit_card"),
    ("Hannah Koh", "e-wallet"), ("Marcus Teo", "credit_card"), ("Siti Aminah", "e-wallet"),
    ("Kelvin Goh", "credit_card"), ("Grace Lee", "e-wallet"), ("Arjun Pillai", "credit_card"),
    ("Natalie Tan", "e-wallet"), ("Farhan Yusof", "credit_card"), ("Chloe Lau", "e-wallet"),
    ("Benedict Ng", "credit_card"), ("Nurul Huda", "e-wallet"), ("Victor Sim", "credit_card"),
    ("Isabelle Chan", "e-wallet"), ("Ethan Wee", "credit_card"),
]
DRIVERS = [
    ("Tan Boon Kiat", "Toyota Corolla Altis", "SJB 3318 P"), ("Mohd Faizal", "Honda Vezel", "SMA 9042 L"),
    ("Lee Chin Hock", "Toyota Prius", "SLK 5521 D"), ("Ramesh Kumar", "Hyundai Ioniq", "SNP 1207 T"),
    ("Wong Kah Seng", "Honda Civic", "SKD 7764 Y"), ("Ahmad Zulkifli", "Toyota Camry", "SGE 4410 H"),
    ("Chua Eng Soon", "Mazda 3", "SMC 2286 K"), ("Subramaniam R", "Kia Cerato", "SLU 6093 B"),
    ("Goh Teck Leong", "Toyota Wish", "SJT 8851 F"), ("Yusuf Ibrahim", "Honda Fit", "SKR 3905 N"),
    ("Lim Ah Beng", "Toyota Vios", "SNC 7712 R"), ("Dinesh Raj", "Hyundai Avante", "SMH 5538 W"),
    ("Teo Wee Kiat", "Honda Jazz", "SLP 1649 E"), ("Hassan Ali", "Toyota Alphard", "SJX 9280 A"),
    ("Ng Soon Huat", "Nissan Sylphy", "SKM 4367 G"), ("Kumar Selvam", "Mazda CX-5", "SNH 2194 J"),
    ("Chen Wei Jie", "Toyota Corolla Cross", "SMT 8023 U"), ("Rashid Osman", "Honda City", "SLB 6711 C"),
    ("Poh Cheng Kok", "BYD Atto 3", "SNK 3350 X"), ("Anand Pillay", "Hyundai Kona", "SMQ 9486 S"),
]


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def _km_scale(lat: float) -> tuple[float, float]:
    return 111.32, 111.32 * math.cos(math.radians(lat))


def _polyline_km(points: list[tuple[float, float]]) -> float:
    return sum(_haversine_m(*points[i], *points[i + 1]) for i in range(len(points) - 1)) / 1000


def _detour_path(a: tuple[float, float], b: tuple[float, float], target_km: float) -> list[tuple[float, float]]:
    """A path a -> via -> b whose haversine length is target_km (bisection on the sideways offset)."""
    ky, kx = _km_scale((a[0] + b[0]) / 2)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    dx, dy = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky
    norm = math.hypot(dx, dy)
    px, py = -dy / norm, dx / norm  # unit vector sideways, in km

    def via(h: float) -> tuple[float, float]:
        return (mid[0] + py * h / ky, mid[1] + px * h / kx)

    lo, hi = 0.0, 80.0
    for _ in range(60):
        h = (lo + hi) / 2
        if _polyline_km([a, via(h), b]) < target_km:
            lo = h
        else:
            hi = h
    return [a, via((lo + hi) / 2), b]


def _along(path: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """n points spread evenly along the polyline, excluding both ends."""
    seg = [_haversine_m(*path[i], *path[i + 1]) for i in range(len(path) - 1)]
    total = sum(seg)
    out = []
    for k in range(1, n + 1):
        d, i = total * k / (n + 1), 0
        while d > seg[i]:
            d -= seg[i]
            i += 1
        f = d / seg[i]
        out.append((path[i][0] + (path[i + 1][0] - path[i][0]) * f, path[i][1] + (path[i + 1][1] - path[i][1]) * f))
    return out


def _profiles(i: int, flagged: bool = False) -> tuple[dict, dict]:
    rn, pay = RIDERS[i]
    dn, car, plate = DRIVERS[i]
    rider = {
        "rider_id": f"R-{9100 + i}", "name": rn, "account_age_days": 120 + 37 * i, "total_trips": 20 + 9 * i,
        "avg_rating": round(4.0 + (i % 6) * 0.15, 1),
        "dispute_history": {"total_disputes": 1 if not flagged else 4, "upheld": 0 if not flagged else 1,
                            "rejected": 1 if not flagged else 3},
        "fraud_flags": 1 if flagged else 0, "fraud_flag_details": "flagged_for_frequent_late_cancellations" if flagged else None,
        "payment_method": pay,
    }
    driver = {
        "driver_id": f"D-{8100 + i}", "name": dn, "account_age_days": 300 + 55 * i, "total_trips": 400 + 170 * i,
        "avg_rating": round(4.5 + (i % 5) * 0.1, 1),
        "dispute_history": {"total_disputes": 1, "upheld_against": 0, "rejected": 1},
        "fraud_flags": 0, "vehicle": f"{car} ({plate})",
    }
    return rider, driver


def _ticket(i: int, dtype: str, desc: str, filed: datetime) -> dict:
    return {"dispute_id": f"DISP-{101 + i}", "trip_id": f"TRIP-2026-{11001 + i}", "filed_by": "rider",
            "dispute_type": dtype, "description": desc, "filed_at": iso(filed), "status": "open"}


# ---------------------------------------------------------------- no-show

def no_show(i, pickup, dropoff, sched, *, arrive_min=-2, wait_min=9, distance_m=0.0, messages=3, calls=1,
            replies=0, gps_missing=False, safety=False, flagged=False, desc=""):
    A, B = PLACES[pickup], PLACES[dropoff]
    arrive = sched + timedelta(minutes=arrive_min)
    cancel = arrive + timedelta(minutes=wait_min)
    rider, driver = _profiles(i, flagged)
    ticket = _ticket(i, "no_show_charge", desc, cancel + timedelta(minutes=25))
    plate = driver["vehicle"]
    ky, _ = _km_scale(A[0])
    stop = (A[0] + distance_m / 1000 / ky, A[1])
    gps = []
    for k, (f, spd) in enumerate(((0.9, 42), (0.55, 36), (0.25, 22), (0.08, 10))):
        gps.append({"timestamp": iso(arrive - timedelta(minutes=12 - 3 * k)),
                    "lat": round(A[0] + 0.02 * f, 6), "lng": round(A[1] + 0.012 * f, 6), "speed_kmh": spd, "status": "en_route"})
    if not gps_missing:
        gps.append({"timestamp": iso(arrive), "lat": round(stop[0], 6), "lng": round(stop[1], 6), "speed_kmh": 0, "status": "arrived"})
        for m in (wait_min // 3, 2 * wait_min // 3):
            if 0 < m < wait_min:
                gps.append({"timestamp": iso(arrive + timedelta(minutes=m)), "lat": round(stop[0], 6), "lng": round(stop[1], 6), "speed_kmh": 0, "status": "waiting"})
    gps.append({"timestamp": iso(cancel), "lat": round(stop[0], 6), "lng": round(stop[1], 6), "speed_kmh": 0, "status": "cancelled"})

    chat, events = [], []
    sec = lambda t, s: t + timedelta(seconds=s)
    chat.append({"timestamp": iso(arrive), "sender": "driver", "type": "message", "content": f"I've arrived at {pickup}. {plate}."})
    texts = ["I'm waiting at the pickup point.", "Hi, are you coming down? I've been waiting a while.",
             "Please let me know, otherwise I'll have to cancel the trip."]
    for n in range(1, messages):
        when = arrive + timedelta(minutes=wait_min * n / (messages + 1)) + timedelta(seconds=20)
        chat.append({"timestamp": iso(when), "sender": "driver", "type": "message", "content": texts[(n - 1) % 3]})
    if messages == 0:
        chat.pop(0)
    call_time = None
    if calls:
        call_time = arrive + timedelta(minutes=wait_min * 0.55)
        chat.append({"timestamp": iso(call_time), "sender": "driver", "type": "call", "content": "Outgoing call to rider — not answered (rang 22s, no response)."})
    reply_texts = ["Coming down now, give me a minute.", "Sorry, five more minutes please."]
    for n in range(replies):
        chat.append({"timestamp": iso(arrive + timedelta(minutes=1 + n * 2, seconds=30)), "sender": "rider", "type": "message", "content": reply_texts[n % 2]})
    if safety:
        chat.append({"timestamp": iso(cancel + timedelta(minutes=3)), "sender": "rider", "type": "message",
                     "content": "The driver was very aggressive and threatened me when I came down. I feel unsafe."})
    chat.append({"timestamp": iso(cancel), "sender": "system", "type": "system",
                 "content": "Trip cancelled by driver. Reason: rider_no_show. Cancellation fee of $5.00 applied."})
    chat.sort(key=lambda c: c["timestamp"])

    t0 = sched - timedelta(minutes=15)
    events += [
        {"timestamp": iso(t0), "event_type": "booking_confirmed", "details": f"Rider {rider['rider_id']} booked trip {ticket['trip_id']} from {pickup} to {dropoff}. Scheduled pickup {sched:%H:%M}."},
        {"timestamp": iso(sec(t0, 15)), "event_type": "driver_assigned", "details": f"Driver {driver['driver_id']} ({driver['name']}, {driver['vehicle']}) assigned."},
        {"timestamp": iso(sec(t0, 20)), "event_type": "driver_en_route", "details": "Driver started navigating to pickup location. Live tracking enabled."},
    ]
    if not gps_missing:
        events += [
            {"timestamp": iso(arrive), "event_type": "driver_arrived", "details": "Driver GPS within 10m of pickup point. Speed 0 km/h. Auto-arrival confirmed."},
            {"timestamp": iso(sec(arrive, 5)), "event_type": "rider_notified", "details": "Push notification + in-app alert sent to rider: 'Your driver has arrived.'"},
            {"timestamp": iso(sec(arrive, 10)), "event_type": "wait_timer_started", "details": f"Free wait timer started. 5 min free wait period ends at {(arrive + timedelta(minutes=5)):%H:%M}."},
        ]
    if call_time:
        events.append({"timestamp": iso(call_time), "event_type": "driver_called_rider", "details": "Driver initiated in-app call to rider. Call rang 22s, no answer."})
    if wait_min >= 5:
        events.append({"timestamp": iso(arrive + timedelta(minutes=5, seconds=10)), "event_type": "wait_timer_expired", "details": "Free 5-min wait period expired. Rider had not boarded. Cancellation fee now applicable per policy."})
    events += [
        {"timestamp": iso(cancel), "event_type": "cancellation_fee_applied", "details": f"$5.00 cancellation fee charged to rider payment method ({rider['payment_method']})."},
        {"timestamp": iso(sec(cancel, 5)), "event_type": "driver_released", "details": f"Driver {driver['driver_id']} released from trip. Trip status: cancelled (rider_no_show)."},
    ]
    events.sort(key=lambda e: e["timestamp"])
    trip = {
        "trip_id": ticket["trip_id"], "rider_id": rider["rider_id"], "driver_id": driver["driver_id"],
        "pickup_location": {"name": pickup, "lat": A[0], "lng": A[1]}, "dropoff_location": {"name": dropoff, "lat": B[0], "lng": B[1]},
        "scheduled_time": iso(sched), "driver_arrival_time": None if gps_missing else iso(arrive),
        "driver_wait_start": None if gps_missing else iso(arrive), "cancellation_time": iso(cancel),
        "cancellation_fee": 5.0, "cancellation_reason": "rider_no_show", "planned_route": None, "fare_breakdown": None,
    }
    return {"dispute_ticket": ticket, "rider_profile": rider, "driver_profile": driver, "trip_data": trip,
            "gps_telemetry": gps, "chat_logs": chat, "app_events": events,
            "cancellation_policy": {"free_wait_time_min": 5, "cancellation_fee_after_wait": 5.0, "no_show_threshold_min": 8, "fee_goes_to": "driver_compensation"}}


# ---------------------------------------------------------------- route deviation

def route(i, pickup, dropoff, sched, *, dev_pct=30.0, fixed=False, detour_chat=False, one_in_trip=False,
          safety=False, flagged=False, desc=""):
    A, B = PLACES[pickup], PLACES[dropoff]
    straight_km = _haversine_m(*A, *B) / 1000
    baseline = straight_km * 1.3
    rider, driver = _profiles(i, flagged)
    start = sched
    ticket_id = f"TRIP-2026-{11001 + i}"
    if one_in_trip:
        path = [A, ((A[0] + B[0]) / 2 + 0.004, (A[1] + B[1]) / 2 + 0.004), B]
        mids = [path[1]]
    else:
        path = _detour_path(A, B, baseline * (1 + dev_pct / 100))
        mids = _along(path, 7)
    actual_km = _polyline_km([A, *mids, B])
    minutes = max(8.0, actual_km / 32 * 60)
    gps = [{"timestamp": iso(start), "lat": A[0], "lng": A[1], "speed_kmh": 0, "status": "trip_started"}]
    for k, (la, lo) in enumerate(mids, start=1):
        gps.append({"timestamp": iso(start + timedelta(minutes=minutes * k / (len(mids) + 1))), "lat": round(la, 6), "lng": round(lo, 6),
                    "speed_kmh": 30 + (k * 7) % 16, "status": "in_trip"})
    end = start + timedelta(minutes=minutes)
    gps.append({"timestamp": iso(end), "lat": B[0], "lng": B[1], "speed_kmh": 0, "status": "trip_completed"})
    per_km, flag = 0.70, 3.50
    if fixed:
        fixed_fare = round(flag + per_km * baseline, 2)
        fare = {"fare_type": "fixed", "actual_fare_sgd": fixed_fare, "per_km_rate_sgd": None, "flag_down_fare_sgd": None,
                "distance_charge_sgd": None, "surge_applied": False, "service_type": "RydeX"}
        actual_fare = fixed_fare
    else:
        dist_charge = round(per_km * actual_km, 2)
        actual_fare = round(flag + dist_charge, 2)
        fare = {"fare_type": "metered", "actual_fare_sgd": actual_fare, "per_km_rate_sgd": per_km, "flag_down_fare_sgd": flag,
                "distance_charge_sgd": dist_charge, "surge_applied": False, "service_type": "RydeTAXI"}
    plate = driver["vehicle"]
    chat = [
        {"timestamp": iso(start - timedelta(minutes=2)), "sender": "driver", "type": "message", "content": f"Hi, I've arrived at {pickup}. {plate}."},
        {"timestamp": iso(start - timedelta(minutes=1)), "sender": "rider", "type": "message", "content": "Coming down now, give me a minute."},
    ]
    if detour_chat:
        chat.append({"timestamp": iso(start + timedelta(minutes=1)), "sender": "rider", "type": "message",
                     "content": "Can we go via the expressway? I heard the main road is jammed."})
        chat.append({"timestamp": iso(start + timedelta(minutes=1, seconds=20)), "sender": "driver", "type": "message", "content": "Sure, I'll take the expressway."})
    else:
        chat.append({"timestamp": iso(start + timedelta(minutes=minutes * 0.5)), "sender": "rider", "type": "message", "content": "Are we going the right way? This seems longer than usual."})
        chat.append({"timestamp": iso(start + timedelta(minutes=minutes * 0.5, seconds=30)), "sender": "driver", "type": "message", "content": "I know this area well, it's fine."})
    if safety:
        chat.append({"timestamp": iso(start + timedelta(minutes=minutes * 0.7)), "sender": "rider", "type": "message",
                     "content": "You are driving recklessly and I feel unsafe. Please slow down."})
    chat.append({"timestamp": iso(end), "sender": "system", "type": "system",
                 "content": f"Trip completed. Fare: ${actual_fare:.2f} ({fare['fare_type']}, {fare['service_type']}). Distance: {actual_km:.2f} km."})
    chat.sort(key=lambda c: c["timestamp"])
    t0 = start - timedelta(minutes=12)
    events = [
        {"timestamp": iso(t0), "event_type": "booking_confirmed", "details": f"Rider {rider['rider_id']} booked trip {ticket_id} from {pickup} to {dropoff}. Scheduled pickup {start:%H:%M}. Service type: {fare['service_type']}."},
        {"timestamp": iso(t0 + timedelta(seconds=15)), "event_type": "driver_assigned", "details": f"Driver {driver['driver_id']} ({driver['name']}, {driver['vehicle']}) assigned. Service type: {fare['service_type']}."},
        {"timestamp": iso(start - timedelta(minutes=2)), "event_type": "driver_arrived", "details": "Driver GPS within 10m of pickup point. Speed 0 km/h. Auto-arrival confirmed."},
        {"timestamp": iso(start), "event_type": "trip_started", "details": "Rider boarded. Trip started." + (f" Fixed fare agreed: ${actual_fare:.2f}." if fixed else f" Metered fare activated. Flag-down: ${flag:.2f}. Per-km rate: ${per_km:.2f}.")},
        {"timestamp": iso(end), "event_type": "trip_completed", "details": f"Trip completed at {dropoff}. Total distance: {actual_km:.2f} km. Total fare: ${actual_fare:.2f}."},
        {"timestamp": iso(end + timedelta(seconds=5)), "event_type": "fare_charged", "details": f"Fare of ${actual_fare:.2f} charged to rider payment method ({rider['payment_method']}). No surge applied."},
    ]
    planned = [{"name": pickup, "lat": A[0], "lng": A[1]},
               {"name": "Planned route", "lat": round((A[0] + B[0]) / 2, 4), "lng": round((A[1] + B[1]) / 2, 4)},
               {"name": dropoff, "lat": B[0], "lng": B[1]}]
    trip = {
        "trip_id": ticket_id, "rider_id": rider["rider_id"], "driver_id": driver["driver_id"],
        "pickup_location": {"name": pickup, "lat": A[0], "lng": A[1]}, "dropoff_location": {"name": dropoff, "lat": B[0], "lng": B[1]},
        "scheduled_time": iso(sched), "driver_arrival_time": iso(start - timedelta(minutes=2)),
        "driver_wait_start": iso(start - timedelta(minutes=2)), "cancellation_time": None, "cancellation_fee": None,
        "cancellation_reason": None, "planned_route": planned, "fare_breakdown": fare,
    }
    ticket = _ticket(i, "route_deviation", desc, end + timedelta(minutes=30))
    events.append({"timestamp": ticket["filed_at"], "event_type": "dispute_filed", "details": "Rider filed route_deviation dispute."})
    return {"dispute_ticket": ticket, "rider_profile": rider, "driver_profile": driver, "trip_data": trip,
            "gps_telemetry": gps, "chat_logs": chat, "app_events": events}


D = lambda m, d, h, mi: datetime(2026, m, d, h, mi)

# (builder, kwargs, expected outcome, expected clauses, label)
SPEC = [
    (no_show, dict(pickup="ION Orchard", dropoff="Changi Airport T3", sched=D(10, 1, 7, 30), arrive_min=-3, wait_min=10, messages=3, calls=1,
                   desc="The driver cancelled and charged me $5 but I was only a couple of minutes away. I do not think I should pay a no-show fee."),
     "charge_upheld", ["NS-1.6"], "Standard no-show: early driver, long wait, message and call, no reply"),
    (no_show, dict(pickup="Jurong East MRT", dropoff="NUS Kent Ridge", sched=D(10, 2, 18, 10), arrive_min=3, wait_min=9, messages=2, calls=1,
                   desc="The driver was late and then cancelled on me. I should not be charged when they turned up after the scheduled time."),
     "charge_upheld", ["NS-1.6"], "No-show upheld although the driver arrived 3 min late (flag only)"),
    (no_show, dict(pickup="Tampines Mall", dropoff="Paya Lebar Quarter", sched=D(10, 3, 12, 0), arrive_min=-2, wait_min=3, messages=2, calls=1,
                   desc="The driver only waited about three minutes before cancelling. I was walking over from the car park."),
     "charge_reversed", ["NS-1.3", "NS-1.7"], "Reversed: cancelled before the 5-minute free wait ended"),
    (no_show, dict(pickup="Junction 8 Bishan", dropoff="Toa Payoh HDB Hub", sched=D(10, 3, 19, 20), arrive_min=-1, wait_min=9, distance_m=150, messages=3, calls=1,
                   desc="I was standing at the pickup point and never saw the car. The driver says they were there but I think they were somewhere else."),
     "charge_reversed", ["NS-1.1", "NS-1.7"], "Reversed: driver GPS 150 m from the pickup point"),
    (no_show, dict(pickup="Woodlands MRT", dropoff="Junction 8 Bishan", sched=D(10, 4, 6, 45), arrive_min=-2, wait_min=9, messages=3, calls=0,
                   desc="The driver sent me texts but never phoned me. I did not see them in time and was charged a no-show fee."),
     "charge_reversed", ["NS-1.5", "NS-1.7"], "Reversed: messages but no call"),
    (no_show, dict(pickup="Bugis Junction", dropoff="Marina Bay Sands", sched=D(10, 4, 21, 0), arrive_min=-2, wait_min=9, messages=0, calls=1,
                   desc="I got one phone call that I missed. There were no messages and I was charged a no-show fee straight away."),
     "charge_reversed", ["NS-1.5", "NS-1.7"], "Reversed: a call but no message"),
    (no_show, dict(pickup="Clementi Mall", dropoff="HarbourFront Centre", sched=D(10, 5, 15, 30), arrive_min=-2, wait_min=11, messages=3, calls=1, replies=2,
                   desc="I told the driver I was coming down and asked for a few more minutes, but they cancelled and charged me."),
     "charge_upheld", ["NS-1.6"], "Upheld although the rider replied twice (replies do not gate the fee)"),
    (no_show, dict(pickup="Waterway Point Punggol", dropoff="NEX Serangoon", sched=D(10, 6, 8, 15), arrive_min=-2, wait_min=6, messages=3, calls=1,
                   desc="The driver cancelled after six minutes. I thought I had at least eight."),
     "charge_reversed", ["NS-1.4", "NS-1.7"], "Reversed: waited 6 min, past the free wait but under the 8-minute no-show threshold"),
    (no_show, dict(pickup="Novena Square", dropoff="Chinatown Point", sched=D(10, 7, 13, 40), arrive_min=-2, wait_min=9, gps_missing=True, messages=3, calls=1,
                   desc="The driver says they arrived but I never got an arrival alert. I do not think they were there."),
     "escalate", ["NS-1.8", "E-1.5"], "Escalate: no GPS arrival record"),
    (no_show, dict(pickup="Leisure Park Kallang", dropoff="ION Orchard", sched=D(10, 8, 22, 5), arrive_min=-2, wait_min=9, messages=3, calls=1, safety=True,
                   desc="The driver shouted at me and threatened me when I got to the car. I want the fee removed and the driver reported."),
     "escalate", ["S-1.1", "S-1.2"], "Escalate: rider reports a threat (safety)"),
    (route, dict(pickup="ION Orchard", dropoff="Marina Bay Sands", sched=D(10, 9, 9, 0), dev_pct=30,
                 desc="The driver took a longer way to Marina Bay Sands and the fare was higher than the app estimate."),
     "refund", ["RD-2.6"], "Metered, 30% longer, no rider request: refund of the extra distance"),
    (route, dict(pickup="Bugis Junction", dropoff="HarbourFront Centre", sched=D(10, 9, 14, 30), dev_pct=25,
                 desc="We went a long way around and the meter ran up. I want the extra distance refunded."),
     "refund", ["RD-2.6"], "Metered, 25% longer: refund"),
    (route, dict(pickup="Novena Square", dropoff="Leisure Park Kallang", sched=D(10, 10, 11, 15), dev_pct=10,
                 desc="The trip felt slightly longer than usual and the fare was a bit higher."),
     "no_action", ["RD-2.2"], "Only 10% longer: under the 20% review threshold"),
    (route, dict(pickup="Toa Payoh HDB Hub", dropoff="Junction 8 Bishan", sched=D(10, 10, 17, 50), dev_pct=35, detour_chat=True,
                 desc="The trip was much longer and more expensive than I expected."),
     "no_action", ["RD-2.3"], "35% longer, but the rider asked for the expressway in chat"),
    (route, dict(pickup="Clementi Mall", dropoff="NUS Kent Ridge", sched=D(10, 11, 8, 40), dev_pct=45, fixed=True,
                 desc="The driver took a long way round on a trip I booked at a fixed price. I think I overpaid."),
     "no_action", ["RD-2.5"], "45% longer on a fixed (up-front) fare: no refund, conduct flag"),
    (route, dict(pickup="Changi Airport T3", dropoff="Marina Bay Sands", sched=D(10, 11, 22, 10), dev_pct=90,
                 desc="The driver went miles out of the way on the way from the airport and the fare was far above normal."),
     "escalate", ["RD-2.8", "E-1.5"], "Huge detour over 2 km, high fare (S$30 or more): escalate, high priority"),
    (route, dict(pickup="Woodlands MRT", dropoff="Junction 8 Bishan", sched=D(10, 12, 7, 20), one_in_trip=True,
                 desc="The driver did not go the way the app showed, but my phone lost signal so I cannot show it."),
     "escalate", ["RD-2.7", "E-1.5"], "Incomplete GPS (one in-trip point): escalate"),
    (route, dict(pickup="NEX Serangoon", dropoff="Junction 8 Bishan", sched=D(10, 12, 20, 25), dev_pct=30, safety=True,
                 desc="The driver took a longer way and drove dangerously fast. I felt scared and want this reported."),
     "escalate", ["S-1.1", "S-1.2"], "Escalate: safety complaint during a route dispute"),
    (route, dict(pickup="Jurong East MRT", dropoff="Clementi Mall", sched=D(10, 13, 10, 5), dev_pct=40,
                 desc="The driver took a very roundabout way to Clementi. I want my money back for the extra distance."),
     "refund", ["RD-2.6"], "Metered, 40% longer on a short trip: refund"),
    (route, dict(pickup="Toa Payoh HDB Hub", dropoff="Novena Square", sched=D(10, 13, 16, 35), dev_pct=60,
                 desc="That was a very short trip but the driver went in a big loop first."),
     "refund", ["RD-2.6"], "Metered, 60% longer on a very short trip: small refund"),
]


def main() -> None:
    expected = {}
    problems = []
    for i, (builder, kw, outcome, clauses, label) in enumerate(SPEC):
        kw = dict(kw)
        data = builder(i, kw.pop("pickup"), kw.pop("dropoff"), kw.pop("sched"), **kw)
        case = DisputeCase.model_validate(data)
        did = data["dispute_ticket"]["dispute_id"]
        saf = safety_override(safety_check(case).facts)
        if data["dispute_ticket"]["dispute_type"] == "no_show_charge":
            got = compute_no_show_outcome(no_show_check(case).facts)
        else:
            got = compute_route_deviation_outcome(route_deviation(case).facts)
        if saf:
            got = saf
        ok = got[0] == outcome and got[2] == clauses
        if not ok:
            problems.append((did, label, got, outcome, clauses))
        (DATA / f"{did}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        expected[did] = {"scenario": label, "dispute_type": data["dispute_ticket"]["dispute_type"],
                         "expected_outcome": outcome, "expected_clauses": clauses, "computed_amount_sgd": got[1]}
        print(f"{did} {'OK ' if ok else 'BAD'} {got[0]:15s} S${got[1]:5.2f} {got[2]}  {label}")
    (DATA / "sample_trips.expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if problems:
        print("\nMISMATCHES:")
        for p in problems:
            print(" ", p)
        sys.exit(1)


if __name__ == "__main__":
    main()
