import argparse
import os
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        exit(1)

def create_invite(code: str, expires_at: str | None) -> None:
    try:
        expires_date = None
        if expires_at:
            expires_date = datetime.strptime(expires_at, "%Y-%m-%d").date()
    except ValueError:
        print("Error: expires date must be in YYYY-MM-DD format.")
        return

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO admin_invite_codes (code, expires_at, used, created_at)
                    VALUES (%s, %s, FALSE, NOW())
                    """,
                    (code, expires_date),
                )
        print(f"Invite code '{code}' created successfully.")
    except psycopg2.IntegrityError:
        print(f"Error: Invite code '{code}' already exists.")
    except Exception as e:
        print(f"Error creating invite: {e}")
    finally:
        conn.close()

def list_invites() -> None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT code, used, expires_at, created_at, used_at
                FROM admin_invite_codes
                ORDER BY created_at DESC
                """
            )
            invites = cur.fetchall()
            if not invites:
                print("No invites found.")
                return
            print(f"{'Code':<20} {'Used':<6} {'Expires At':<12} {'Created At':<20} {'Used At':<20}")
            print("-" * 80)
            for inv in invites:
                expires_str = inv['expires_at'].strftime("%Y-%m-%d") if inv['expires_at'] else "None"
                created_str = inv['created_at'].strftime("%Y-%m-%d %H:%M:%S") if inv['created_at'] else "None"
                used_str = "Yes" if inv['used'] else "No"
                used_at_str = inv['used_at'].strftime("%Y-%m-%d %H:%M:%S") if inv['used_at'] else "None"
                print(f"{inv['code']:<20} {used_str:<6} {expires_str:<12} {created_str:<20} {used_at_str:<20}")
    except Exception as e:
        print(f"Error listing invites: {e}")
    finally:
        conn.close()

def expire_invite(code: str) -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE admin_invite_codes
                    SET used = TRUE, used_at = NOW()
                    WHERE code = %s AND used = FALSE
                    """,
                    (code,),
                )
                if cur.rowcount == 0:
                    print(f"No unused invite found with code '{code}'.")
                else:
                    print(f"Invite code '{code}' marked as used (expired).")
    except Exception as e:
        print(f"Error expiring invite: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Manage admin invite codes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create_invite", help="Create a new invite code.")
    create_parser.add_argument("--code", required=True, help="Invite code to create.")
    create_parser.add_argument("--expires", help="Expiration date in YYYY-MM-DD format (optional).")

    list_parser = subparsers.add_parser("list_invites", help="List all invite codes.")

    expire_parser = subparsers.add_parser("expire_invite", help="Mark an invite code as used (expired).")
    expire_parser.add_argument("--code", required=True, help="Invite code to expire.")

    args = parser.parse_args()

    if args.command == "create_invite":
        create_invite(args.code, args.expires)
    elif args.command == "list_invites":
        list_invites()
    elif args.command == "expire_invite":
        expire_invite(args.code)

if __name__ == "__main__":
    main()
