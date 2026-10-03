"""
scripts/marketplace_discovery.py
Real Snowflake Marketplace Discovery & Import Script.

Steps:
1. Account capabilities audit
2. Discover all available listings (SHOW AVAILABLE LISTINGS)
3. Filter: free, importable, not-application, not-by-request
4. Rank by manufacturing relevance (Tier 1-4)
5. Test import of top candidates via CREATE DATABASE ... FROM LISTING
6. Explore schemas, tables, views, columns, row counts
7. Output: Selected listing report

Cross-region Marketplace terms have been accepted.
"""

import os
import sys
import json
import hashlib
import platform
from datetime import datetime

# Fix for Windows Store Python 3.13 reparse point bug in platform.libc_ver
platform.libc_ver = lambda *args, **kwargs: ("", "")

sys.stdout.reconfigure(encoding='utf-8')


def safe_str(val):
    if val is None:
        return ""
    return str(val).encode("ascii", "ignore").decode("ascii")


def row_to_dict(row):
    try:
        return row.as_dict()
    except Exception:
        pass
    try:
        return dict(row)
    except Exception:
        return {"raw": str(row)}


def load_snowflake_config():
    cfg = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "user": os.environ.get("SNOWFLAKE_USER", ""),
        "password": os.environ.get("SNOWFLAKE_PASSWORD", ""),
        "role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH"),
        "database": os.environ.get("SNOWFLAKE_DATABASE", "PM_OEE_DB"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),
    }
    if not cfg["password"]:
        secrets_path = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                import tomllib
                with open(secrets_path, "rb") as f:
                    sec = tomllib.load(f)
                    if "snowflake" in sec:
                        for k, v in sec["snowflake"].items():
                            cfg[k] = v
            except Exception:
                try:
                    import toml
                    with open(secrets_path, "r", encoding="utf-8") as f:
                        sec = toml.load(f)
                        if "snowflake" in sec:
                            for k, v in sec["snowflake"].items():
                                cfg[k] = v
                except Exception:
                    pass
    return cfg


def main():
    from snowflake.snowpark import Session

    cfg = load_snowflake_config()
    if not cfg.get("password"):
        print("ERROR: SNOWFLAKE_PASSWORD env var or .streamlit/secrets.toml password not found")
        sys.exit(1)

    session = Session.builder.configs(cfg).create()
    report = {}

    # ================================================================
    # STEP 1: ACCOUNT CAPABILITIES
    # ================================================================
    print("=" * 70)
    print("STEP 1: ACCOUNT CAPABILITIES")
    print("=" * 70)

    for q in [
        "SELECT CURRENT_ACCOUNT() AS V",
        "SELECT CURRENT_USER() AS V",
        "SELECT CURRENT_ROLE() AS V",
        "SELECT CURRENT_REGION() AS V",
        "SELECT CURRENT_VERSION() AS V",
    ]:
        try:
            r = session.sql(q).collect()[0]
            label = q.split("CURRENT_")[1].split("()")[0]
            val = safe_str(r[0])
            print(f"  {label}: {val}")
            report[label] = val
        except Exception as e:
            print(f"  {q}: ERROR - {safe_str(e)}")

    # ================================================================
    # STEP 2: DISCOVER ALL AVAILABLE LISTINGS
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 2: DISCOVER AVAILABLE LISTINGS")
    print("=" * 70)

    try:
        all_listings = session.sql("SHOW AVAILABLE LISTINGS").collect()
        total = len(all_listings)
        print(f"  Total available listings: {total}")
        report["total_listings"] = total
    except Exception as e:
        print(f"  SHOW AVAILABLE LISTINGS failed: {safe_str(e)}")
        print("\n  MARKETPLACE NOT AVAILABLE - cannot proceed")
        session.close()
        return

    if total == 0:
        print("\n  No listings available")
        session.close()
        return

    # Get column names
    d0 = row_to_dict(all_listings[0])
    cols = list(d0.keys())
    print(f"  Listing columns: {cols}")

    # ================================================================
    # STEP 3: FILTER FREE + IMPORTABLE
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 3: FILTER FREE + IMPORTABLE")
    print("=" * 70)

    # Previously tested listings that failed - skip those
    SKIP_GLOBAL_NAMES = {"GZSOZ1LLD8", "GZSOZ1LLE9", "GZSOZ1LLEL",
                         "GZSOZBT22EH", "GZSOZBT22EL", "GZSOZBT22ET"}

    free_importable = []

    for row in all_listings:
        d = row_to_dict(row)
        global_name = safe_str(d.get("global_name", ""))
        title = safe_str(d.get("title", ""))
        is_monetized = safe_str(d.get("is_monetized", "")).lower()
        is_ready = safe_str(d.get("is_ready_for_import", "")).lower()
        is_imported = safe_str(d.get("is_imported", "")).lower()
        is_by_request = safe_str(d.get("is_by_request", "")).lower()
        is_application = safe_str(d.get("is_application", "")).lower()
        regions = safe_str(d.get("regions", ""))
        provider = safe_str(d.get("provider_name", d.get("provider", "")))

        # Skip previously blocked
        if global_name in SKIP_GLOBAL_NAMES:
            continue

        # Skip monetized (paid)
        if is_monetized == "true":
            continue

        # Skip applications (native apps, not data)
        if is_application == "true":
            continue

        # Skip by-request
        if is_by_request == "true":
            continue

        # Only importable
        if is_ready != "true":
            continue

        entry = {
            "global_name": global_name,
            "title": title,
            "provider": provider,
            "is_ready_for_import": is_ready,
            "is_imported": is_imported,
            "regions": regions[:120],
            "is_monetized": is_monetized,
        }
        free_importable.append(entry)

    print(f"  Free + importable candidates: {len(free_importable)}")

    # ================================================================
    # STEP 4: RANK BY MANUFACTURING RELEVANCE
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 4: MANUFACTURING RELEVANCE RANKING")
    print("=" * 70)

    tier1_kw = ["manufactur", "machine", "telemetry", "iot", "sensor",
                "vibration", "predictive maintenance", "equipment",
                "failure", "rpm", "cnc", "industrial equipment"]
    tier2_kw = ["industrial", "production", "supply chain", "spare part",
                "factory", "plant", "motor", "pump", "bearing",
                "supplier", "procurement", "logistics", "inventory"]
    tier3_kw = ["weather", "climate", "temperature", "energy", "power",
                "humidity", "environmental", "geospatial", "location"]

    def rank_listing(entry):
        text = entry["title"].lower()
        for kw in tier1_kw:
            if kw in text:
                return 1, kw
        for kw in tier2_kw:
            if kw in text:
                return 2, kw
        for kw in tier3_kw:
            if kw in text:
                return 3, kw
        return 4, ""

    ranked = []
    for c in free_importable:
        tier, kw = rank_listing(c)
        c["tier"] = tier
        c["matched_keyword"] = kw
        ranked.append(c)

    ranked.sort(key=lambda x: x["tier"])

    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in ranked:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1

    print(f"  Tier 1 (Manufacturing/IoT): {tier_counts[1]}")
    print(f"  Tier 2 (Industrial/Supply Chain): {tier_counts[2]}")
    print(f"  Tier 3 (Weather/Energy): {tier_counts[3]}")
    print(f"  Tier 4 (Other): {tier_counts[4]}")

    print("\n  Top 20 candidates by relevance:")
    for i, c in enumerate(ranked[:20]):
        print(f"  [{i+1}] Tier {c['tier']} | {c['title'][:65]}")
        print(f"       Global: {c['global_name']} | Provider: {c['provider'][:40]} | Kw: '{c['matched_keyword']}'")

    # ================================================================
    # STEP 5: TEST ACTUAL IMPORTS (top 5 candidates)
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 5: TEST ACTUAL IMPORTS (Testing top 5 candidates)")
    print("=" * 70)

    test_candidates = ranked[:5]
    if not test_candidates:
        print("  No candidates available for import testing.")
        session.close()
        return

    results = []
    successful = None

    for i, candidate in enumerate(test_candidates):
        gn = candidate["global_name"]
        title = candidate["title"]
        db_name = f"MKT_REAL_{i+1}"

        print(f"\n  --- Test {i+1}/5: {title[:55]} ({gn}) ---")

        try:
            session.sql(f"DROP DATABASE IF EXISTS {db_name}").collect()
            import_sql = f"CREATE DATABASE {db_name} FROM LISTING '{gn}'"
            print(f"  SQL: {import_sql}")
            session.sql(import_sql).collect()
            print(f"  RESULT: IMPORT SUCCESSFUL!")

            # Verify database
            print(f"  Verifying database {db_name}...")
            schemas = session.sql(f"SHOW SCHEMAS IN DATABASE {db_name}").collect()
            schema_names = [
                safe_str(row_to_dict(s).get("name"))
                for s in schemas
                if safe_str(row_to_dict(s).get("name")) != "INFORMATION_SCHEMA"
            ]
            print(f"  Schemas: {schema_names}")

            table_info = []
            column_info = {}

            for sname in schema_names:
                # Tables
                try:
                    tables = session.sql(f'SHOW TABLES IN {db_name}."{sname}"').collect()
                    for t in tables:
                        td = row_to_dict(t)
                        tname = safe_str(td.get("name"))
                        try:
                            cnt = session.sql(
                                f'SELECT COUNT(*) AS CNT FROM {db_name}."{sname}"."{tname}"'
                            ).collect()[0]["CNT"]
                            print(f"    Table {sname}.{tname} -> {cnt:,} rows")
                            table_info.append({
                                "schema": sname, "table": tname,
                                "rows": cnt, "is_view": False
                            })

                            # Get column details
                            try:
                                cols_rows = session.sql(
                                    f'DESCRIBE TABLE {db_name}."{sname}"."{tname}"'
                                ).collect()
                                col_list = []
                                for cr in cols_rows:
                                    cd = row_to_dict(cr)
                                    col_list.append({
                                        "name": safe_str(cd.get("name")),
                                        "type": safe_str(cd.get("type")),
                                        "nullable": safe_str(cd.get("null?")),
                                    })
                                column_info[f"{sname}.{tname}"] = col_list
                                print(f"      Columns ({len(col_list)}): "
                                      + ", ".join(c["name"] for c in col_list[:10])
                                      + ("..." if len(col_list) > 10 else ""))
                            except Exception as ce:
                                print(f"      Column describe error: {safe_str(ce)[:80]}")
                        except Exception as ce:
                            print(f"    Table {sname}.{tname} COUNT error: {safe_str(ce)[:80]}")
                except Exception as te:
                    print(f"    Tables listing error in {sname}: {safe_str(te)[:80]}")

                # Views (if no tables found)
                if not table_info:
                    try:
                        views = session.sql(f'SHOW VIEWS IN {db_name}."{sname}"').collect()
                        for v in views:
                            vd = row_to_dict(v)
                            vname = safe_str(vd.get("name"))
                            try:
                                cnt = session.sql(
                                    f'SELECT COUNT(*) AS CNT FROM {db_name}."{sname}"."{vname}"'
                                ).collect()[0]["CNT"]
                                print(f"    View {sname}.{vname} -> {cnt:,} rows")
                                table_info.append({
                                    "schema": sname, "table": vname,
                                    "rows": cnt, "is_view": True
                                })

                                # Columns for views
                                try:
                                    cols_rows = session.sql(
                                        f'DESCRIBE VIEW {db_name}."{sname}"."{vname}"'
                                    ).collect()
                                    col_list = []
                                    for cr in cols_rows:
                                        cd = row_to_dict(cr)
                                        col_list.append({
                                            "name": safe_str(cd.get("name")),
                                            "type": safe_str(cd.get("type")),
                                        })
                                    column_info[f"{sname}.{vname}"] = col_list
                                    print(f"      Columns ({len(col_list)}): "
                                          + ", ".join(c["name"] for c in col_list[:10])
                                          + ("..." if len(col_list) > 10 else ""))
                                except Exception:
                                    pass
                            except Exception as ve:
                                print(f"    View {sname}.{vname} COUNT error: {safe_str(ve)[:80]}")
                    except Exception:
                        pass

            # Sample data from first table
            if table_info:
                first = table_info[0]
                obj_type = "VIEW" if first.get("is_view") else "TABLE"
                try:
                    sample = session.sql(
                        f'SELECT * FROM {db_name}."{first["schema"]}"."{first["table"]}" LIMIT 3'
                    ).collect()
                    print(f"\n  Sample data from {first['schema']}.{first['table']}:")
                    for sr in sample:
                        sd = row_to_dict(sr)
                        # Print first 5 columns
                        preview_keys = list(sd.keys())[:5]
                        preview = {k: safe_str(sd[k])[:40] for k in preview_keys}
                        print(f"    {preview}")
                except Exception as se:
                    print(f"  Sample query error: {safe_str(se)[:80]}")

            result = {
                "candidate_num": i + 1,
                "title": title,
                "global_name": gn,
                "provider": candidate["provider"],
                "db_name": db_name,
                "status": "SUCCESS",
                "tier": candidate["tier"],
                "keyword": candidate["matched_keyword"],
                "tables": table_info,
                "schemas": schema_names,
                "columns": column_info,
            }
            results.append(result)
            successful = result

            print(f"\n  >>> SUCCESSFUL MARKETPLACE IMPORT CONFIRMED! <<<")
            break

        except Exception as e:
            err = safe_str(e)
            if "Cross Region" in err or "cross region" in err.lower():
                err_class = "CROSS_REGION_TERMS"
            elif "organization" in err.lower():
                err_class = "ORGANIZATION_POLICY"
            elif "privilege" in err.lower() or "access" in err.lower():
                err_class = "PRIVILEGE"
            else:
                err_class = "OTHER"

            print(f"  RESULT: IMPORT FAILED")
            print(f"  Classification: {err_class}")
            print(f"  Error: {err[:200]}")

            results.append({
                "candidate_num": i + 1,
                "title": title,
                "global_name": gn,
                "db_name": db_name,
                "status": "FAILED",
                "error_class": err_class,
                "error": err[:300],
                "tier": candidate["tier"],
            })

    # ================================================================
    # STEP 6: FINAL REPORT
    # ================================================================
    print("\n" + "=" * 70)
    print("FINAL MARKETPLACE DISCOVERY REPORT")
    print("=" * 70)

    print(f"\nAccount: {report.get('ACCOUNT', '?')}")
    print(f"Region: {report.get('REGION', '?')}")
    print(f"Total Available Listings: {report.get('total_listings', '?')}")
    print(f"Candidates Tested: {len(results)}")

    for r in results:
        t = r["title"][:50]
        gn = r.get("global_name", "?")
        st = r["status"]
        if st == "SUCCESS":
            print(f"  [{r['candidate_num']}] PASS: {t} ({gn}) -> DB: {r['db_name']}")
        else:
            print(f"  [{r['candidate_num']}] FAIL: {t} ({gn}) -> {r.get('error_class')}: {r.get('error', '')[:80]}")

    if successful:
        print(f"\n{'=' * 70}")
        print("SELECTED MARKETPLACE LISTING")
        print(f"{'=' * 70}")
        print(f"  Title:       {successful['title']}")
        print(f"  Provider:    {successful['provider']}")
        print(f"  Global Name: {successful['global_name']}")
        print(f"  Database:    {successful['db_name']}")
        print(f"  Schemas:     {successful['schemas']}")
        print(f"  Tier:        {successful['tier']} (keyword: '{successful['keyword']}')")
        print(f"  Tables:")
        for t in successful["tables"]:
            typ = "VIEW" if t.get("is_view") else "TABLE"
            print(f"    {t['schema']}.{t['table']} ({typ}) -> {t['rows']:,} rows")
        print(f"\n  Column Details:")
        for tbl_name, cols in successful.get("columns", {}).items():
            print(f"    {tbl_name}:")
            for c in cols:
                print(f"      {c['name']:30s} {c['type']}")

        # Write report JSON for downstream consumption
        report_path = os.path.join(os.path.dirname(__file__), "..",
                                   "marketplace_selected_listing.json")
        listing_report = {
            "title": successful["title"],
            "provider": successful["provider"],
            "global_name": successful["global_name"],
            "database": successful["db_name"],
            "schemas": successful["schemas"],
            "tier": successful["tier"],
            "keyword": successful["keyword"],
            "tables": successful["tables"],
            "columns": successful.get("columns", {}),
            "discovered_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(listing_report, f, indent=2, default=str)
        print(f"\n  Report saved to: {report_path}")

        print(f"\n  RECOMMENDATION: MARKETPLACE AVAILABLE - PROCEED WITH INGESTION")
    else:
        print("\n  MARKETPLACE ACCESS: ALL CANDIDATES FAILED")
        print("  RECOMMENDATION: Review errors and retry with different candidates")

    session.close()


if __name__ == "__main__":
    main()
