import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    
    plot_id = "69de624047f8c01c4979d381"
    plot = await db.plot.find_unique(where={"id": plot_id})
    if not plot:
        print(f"Plot {plot_id} not found!")
        await db.disconnect()
        return

    print(f"=== PLOT {plot_id} ===")
    print(f"Name: {plot.name}")
    print(f"Latitude: {plot.latitude}, Longitude: {plot.longitude}")
    print(f"GeoJSON: {plot.geoJson[:300]}...")

    # Fetch the latest snapshot
    from prisma.models import IntelligenceSnapshot
    snap = await db.intelligencesnapshot.find_first(
        where={"plotId": plot_id},
        order={"capturedAt": "desc"}
    )
    if snap:
        print(f"Snapshot found, captured at {snap.capturedAt}")
        print(f"Surface stats keys: {snap.surfaceStats.keys() if snap.surfaceStats else 'None'}")
    
    await db.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
