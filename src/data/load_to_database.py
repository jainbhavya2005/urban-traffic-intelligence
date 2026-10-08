import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "traffic_db",
    "user": "traffic_user",
    "password": "traffic_password",
}


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# --------------------------------------------------
# Load one GeoJSON file
# --------------------------------------------------

def load_one_day(file_path):

    print(f"Loading: {file_path.name}")

    with open(file_path, "r") as f:
        data = json.load(f)

    roads = []
    traffic_readings = []

    for feature in data["features"]:

        geometry = feature.get("geometry")
        properties = feature.get("properties", {})

        # Skip metadata feature
        if geometry is None:
            continue

        segment_id = properties["segmentId"]
        new_segment_id = properties.get("newSegmentId")
        speed_limit = properties.get("speedLimit")
        frc = properties.get("frc")
        street_name = properties.get("streetName")
        distance = properties.get("distance")

        roads.append(
            (
                segment_id,
                new_segment_id,
                street_name,
                speed_limit,
                frc,
                distance,
                json.dumps(geometry),
            )
        )

        # --------------------------------------------------
        # Hourly traffic observations
        # --------------------------------------------------

        for observation in properties["segmentProbeCounts"]:

            time_set = observation["timeSet"]
            probe_count = observation["probeCount"]

            # timeSet 2 = 00:00
            # timeSet 3 = 01:00
            # ...
            # timeSet 25 = 23:00
            hour = time_set - 2

            # Date comes from the filename
            date = file_path.name.split("__")[1].split("_to_")[0]

            timestamp = f"{date} {hour:02d}:00:00"

            traffic_readings.append(
                (
                    segment_id,
                    timestamp,
                    probe_count,
                )
            )

    print(f"Road records prepared: {len(roads):,}")
    print(f"Traffic records prepared: {len(traffic_readings):,}")

    return roads, traffic_readings


# --------------------------------------------------
# Insert roads
# --------------------------------------------------

def insert_roads(conn, roads):

    query = """
        INSERT INTO roads (
            segment_id,
            new_segment_id,
            street_name,
            speed_limit,
            frc,
            distance,
            geometry
        )
        VALUES %s
        ON CONFLICT (segment_id) DO NOTHING
    """

    with conn.cursor() as cursor:

        execute_values(
            cursor,
            query,
            roads,
            template="""
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    ST_SetSRID(
                        ST_GeomFromGeoJSON(%s),
                        4326
                    )
                )
            """,
            page_size=5000,
        )


# --------------------------------------------------
# Insert traffic readings
# --------------------------------------------------

def insert_traffic_readings(conn, traffic_readings):

    query = """
        INSERT INTO traffic_readings (
            road_id,
            timestamp,
            probe_count
        )
        SELECT
            roads.id,
            data.timestamp::timestamptz,
            data.probe_count
        FROM (
            VALUES %s
        ) AS data(
            segment_id,
            timestamp,
            probe_count
        )
        JOIN roads
            ON roads.segment_id = data.segment_id
        ON CONFLICT (road_id, timestamp) DO NOTHING
    """

    with conn.cursor() as cursor:

        execute_values(
            cursor,
            query,
            traffic_readings,
            template="(%s, %s, %s)",
            page_size=10000,
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    # Find all GeoJSON files
    files = sorted(
        RAW_DATA_PATH.glob("*.geojson")
    )

    if not files:

        raise FileNotFoundError(
            f"No GeoJSON files found in {RAW_DATA_PATH}"
        )

    print("=" * 60)
    print("URBAN TRAFFIC DATABASE INGESTION")
    print("=" * 60)

    print(f"Raw data directory: {RAW_DATA_PATH}")
    print(f"Files found: {len(files)}")

    # --------------------------------------------------
    # Connect to PostgreSQL
    # --------------------------------------------------

    conn = get_connection()

    try:

        # --------------------------------------------------
        # Process every GeoJSON file
        # --------------------------------------------------

        for i, file_path in enumerate(files, start=1):

            print("\n" + "=" * 60)
            print(f"PROCESSING FILE {i}/{len(files)}")
            print(f"File: {file_path.name}")
            print("=" * 60)

            # ----------------------------------------------
            # Parse GeoJSON
            # ----------------------------------------------

            roads, traffic_readings = load_one_day(
                file_path
            )

            # ----------------------------------------------
            # Insert roads
            # ----------------------------------------------

            print("\nInserting roads...")

            insert_roads(
                conn,
                roads
            )

            print("Road insertion complete.")

            # ----------------------------------------------
            # Insert traffic readings
            # ----------------------------------------------

            print("\nInserting traffic readings...")

            insert_traffic_readings(
                conn,
                traffic_readings
            )

            print("Traffic insertion complete.")

            # ----------------------------------------------
            # Commit this day's transaction
            # ----------------------------------------------

            conn.commit()

            print(
                f"File {i}/{len(files)} "
                "committed successfully."
            )

        # --------------------------------------------------
        # All files completed
        # --------------------------------------------------

        print("\n" + "=" * 60)
        print("ALL FILES PROCESSED SUCCESSFULLY")
        print("=" * 60)

    except Exception:

        # Roll back the current day's transaction
        conn.rollback()

        print("\nERROR — transaction rolled back.")

        raise

    finally:

        conn.close()

    print("\nDatabase ingestion completed.")


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    main()