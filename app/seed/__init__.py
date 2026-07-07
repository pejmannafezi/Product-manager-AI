from app import db as dbmod
from app.config import SEED_VERSION
from app.seed import checklist_templates, compliance_rules, glossary_seed


def run_seeds(conn):
    if dbmod.get_setting(conn, "seed_version") == SEED_VERSION:
        return
    checklist_templates.seed(conn)
    compliance_rules.seed(conn)
    glossary_seed.seed(conn)
    dbmod.set_setting(conn, "seed_version", SEED_VERSION)
