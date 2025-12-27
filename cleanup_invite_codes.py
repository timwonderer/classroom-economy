#!/usr/bin/env python3
"""
One-time script to clean up invite codes with leading/trailing whitespace.
This fixes the issue where invite codes created before the whitespace fix
still have whitespace in the database and fail validation.
"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def cleanup_invite_codes():
    """Strip whitespace from all invite codes in the database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return

    try:
        with conn:
            with conn.cursor() as cur:
                # Get all invite codes
                cur.execute("SELECT id, code FROM admin_invite_codes")
                codes = cur.fetchall()

                if not codes:
                    print("No invite codes found in database.")
                    return

                print(f"Found {len(codes)} invite codes. Checking for whitespace...")
                updated = 0

                for code_id, code in codes:
                    stripped = code.strip()
                    if code != stripped:
                        print(f"  Updating: {repr(code)} -> {repr(stripped)}")
                        cur.execute(
                            "UPDATE admin_invite_codes SET code = %s WHERE id = %s",
                            (stripped, code_id)
                        )
                        updated += 1

                conn.commit()
                print(f"\n✅ Cleanup complete: {updated} codes updated, {len(codes) - updated} already clean")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Invite Code Cleanup Script")
    print("=" * 60)
    cleanup_invite_codes()
