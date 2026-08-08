
def test_extras_functions_exist():
    from app.services.arr_db_migrator import migrate_radarr_extras_sqlite, migrate_sonarr_extras_sqlite
    assert callable(migrate_radarr_extras_sqlite)
