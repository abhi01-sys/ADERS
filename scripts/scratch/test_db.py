"""Quick test for the database layer."""
import sys
sys.path.insert(0, r"c:\Users\Abhishek\OneDrive\Documents\V sem\ADERS")

from database.db import engine, Base
from database.models import Incident, Alert, Acknowledgement
from database.db import SessionLocal
from database import crud

Base.metadata.create_all(bind=engine)
print("✅ Tables created: incidents, alerts, acknowledgements")

db = SessionLocal()

inc = crud.create_incident(
    db,
    camera_id="cam_001",
    confidence=0.87,
    severity="major",
    location_lat=28.6139,
    location_lon=77.2090,
    snapshot_path="media/snapshots/test.jpg",
    clip_path="media/clips/test.mp4",
)
print(f"✅ Incident created: ID={inc.id}, severity={inc.severity}, confidence={inc.confidence}")

acked = crud.acknowledge_incident(db, inc.id, responder="Test User", message="All good")
print(f"✅ Acknowledged: ack={acked.acknowledged}, ack_at={acked.ack_at}")

all_inc = crud.get_all_incidents(db)
print(f"✅ Total incidents in DB: {len(all_inc)}")

# Print as dict
print("\nIncident dict preview:")
for k, v in inc.to_dict().items():
    print(f"  {k}: {v}")

db.close()
print("\n✅ Database layer working correctly!")

