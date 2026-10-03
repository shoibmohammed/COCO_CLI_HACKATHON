"""
scripts/test_all_marketplace_imports.py
Test ALL free importable Marketplace listings in the account to find any listing that imports successfully without error.
"""

import os
import sys
import json
import platform

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, ".")

platform.libc_ver = lambda *args, **kwargs: ("", "")

from scripts.marketplace_discovery import load_snowflake_config, row_to_dict
from snowflake.snowpark import Session


def main():
    cfg = load_snowflake_config()
    session = Session.builder.configs(cfg).create()

    print("Fetching all available listings...")
    all_listings = session.sql("SHOW AVAILABLE LISTINGS").collect()
    print(f"Total available listings: {len(all_listings)}")

    importable = []
    for r in all_listings:
        d = row_to_dict(r)
        is_monetized = str(d.get("is_monetized", "")).lower()
        is_ready = str(d.get("is_ready_for_import", "")).lower()
        is_by_request = str(d.get("is_by_request", "")).lower()
        is_app = str(d.get("is_application", "")).lower()

        if is_monetized != "true" and is_ready == "true" and is_by_request != "true" and is_app != "true":
            importable.append(d)

    print(f"Total candidate importable listings to test: {len(importable)}")

    successes = []
    failures = []

    for i, d in enumerate(importable):
        gn = d.get("global_name", "")
        title = d.get("title", "")
        provider = d.get("provider_name", d.get("organization_profile_name", "Unknown"))
        db_name = f"MKT_TEST_RUN_{i+1}"

        print(f"[{i+1}/{len(importable)}] Testing: {title[:50]} ({gn})...")

        try:
            session.sql(f"DROP DATABASE IF EXISTS {db_name}").collect()
            session.sql(f"CREATE DATABASE {db_name} FROM LISTING '{gn}'").collect()
            print(f"  --> SUCCESS! Imported {title} as {db_name}")

            # Inspect schemas and tables
            schemas = session.sql(f"SHOW SCHEMAS IN DATABASE {db_name}").collect()
            schema_names = [
                row_to_dict(s).get("name") for s in schemas
                if row_to_dict(s).get("name") != "INFORMATION_SCHEMA"
            ]

            tables_info = []
            for sname in schema_names:
                try:
                    tbls = session.sql(f'SHOW TABLES IN DATABASE {db_name}."{sname}"').collect()
                    for t in tbls:
                        td = row_to_dict(t)
                        tname = td.get("name")
                        try:
                            cnt = session.sql(f'SELECT COUNT(*) AS CNT FROM {db_name}."{sname}"."{tname}"').collect()[0]["CNT"]
                            tables_info.append({"schema": sname, "table": tname, "rows": cnt})
                        except Exception:
                            tables_info.append({"schema": sname, "table": tname, "rows": "?"})
                except Exception:
                    pass

            item = {
                "title": title,
                "provider": provider,
                "global_name": gn,
                "database": db_name,
                "schemas": schema_names,
                "tables": tables_info,
            }
            successes.append(item)

            # Save first working listing immediately
            with open("marketplace_selected_listing.json", "w", encoding="utf-8") as f:
                json.dump(item, f, indent=2, default=str)
            print(f"Saved working listing to marketplace_selected_listing.json!")
            break

        except Exception as e:
            err = str(e)
            failures.append({"title": title, "global_name": gn, "error": err[:150]})
            if "terms" in err.lower():
                print(f"  --> Failed: Terms not accepted ({err[:90]})")
            else:
                print(f"  --> Failed: {err[:90]}")

    print("\n================ SUMMARY ================")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")

    session.close()


if __name__ == "__main__":
    main()
