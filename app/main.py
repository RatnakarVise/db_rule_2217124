from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import re
import json

app = FastAPI(title="S4HANA Credit Management Object Remediator")

# Mapping of obsolete objects to their replacements (if available)
REPLACEMENTS = {
    "S066": "UKM_ITEM (item level credit data, per SAP Note 2706489)",
    "S067": "UKM_ITEM (item level credit data, per SAP Note 2706489)",
    "SD_VKMLOG_SHOW": "This is obsolete",
    "VAKCR_REBUILD": "This is obsolete",
    "RVKRED03": "This is obsolete",
    "RVKRED04": "This is obsolete",
    "RVKRED05": "This is obsolete",
    "VKMI": "This is obsolete",
    "VAKCR": "This is obsolete",
    "VKM2": "UKM_CASE (OSS Note 2270544)",
    "VKM3": "UKM_CASE (OSS Note 2270544)",
    "VKM5": "UKM_CASE (OSS Note 2270544)",
    "CL_CRED_VAL_LOG": "This is obsolete",
}

# Categorise by ABAP usage context
TABLES = ["S066", "S067", "VKMI", "VAKCR"]
TRANSACTIONS = ["VKM2", "VKM3", "VKM5"]
PROGRAMS = ["SD_VKMLOG_SHOW", "VAKCR_REBUILD", "RVKRED03", "RVKRED04", "RVKRED05"]
CLASSES = ["CL_CRED_VAL_LOG"]

# Context-aware regex patterns
TABLE_RE = re.compile(
    rf"(?P<full>(?P<stmt>\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bMODIFY\b)[\s\S]*?\b(FROM|INTO|UPDATE|DELETE\s+FROM)\b\s+(?P<obj>{'|'.join(TABLES)})\b)",
    re.IGNORECASE,
)
TXN_RE = re.compile(
    rf"(?P<full>(?P<stmt>\bCALL\s+TRANSACTION\b)\s+['\"]?(?P<obj>{'|'.join(TRANSACTIONS)})['\"]?)",
    re.IGNORECASE,
)
PROG_RE = re.compile(
    rf"(?P<full>(?P<stmt>\bSUBMIT\b)\s+(?P<obj>{'|'.join(PROGRAMS)})\b)",
    re.IGNORECASE,
)
CLASS_RE = re.compile(
    rf"(?P<full>(?P<stmt>\bCREATE\s+OBJECT\b|\bNEW\b|\bTYPE\s+REF\s+TO\b)[\s\S]*?\b(?P<obj>{'|'.join(CLASSES)})\b)",
    re.IGNORECASE,
)

# All patterns to search
FINDERS = [TABLE_RE, TXN_RE, PROG_RE, CLASS_RE]

class Unit(BaseModel):
    pgm_name: str
    inc_name: str
    type: str
    name: Optional[str] = None
    class_implementation: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    code: Optional[str] = ""

def find_obsolete_usage(txt: str):
    matches = []
    for pat in FINDERS:
        for m in pat.finditer(txt or ""):
            matches.append({
                "full": m.group("full"),
                "stmt": m.group("stmt"),
                "object": m.group("obj"),
                "suggested_statement": REPLACEMENTS.get(m.group("obj").upper()),
                "span": m.span("full"),
            })
    matches.sort(key=lambda x: x["span"][0])
    return matches

@app.post("/remediate-credit-objects")
def remediate_credit_objects(units: List[Unit]):
    results = []
    for u in units:
        src = u.code or ""
        metadata = []
        for m in find_obsolete_usage(src):
            metadata.append({
                "table": None,
                "target_type": None,
                "target_name": m["object"],
                "start_char_in_unit": m["span"][0],
                "end_char_in_unit": m["span"][1],
                "used_fields": [],
                "ambiguous": m["suggested_statement"] is None,
                "suggested_statement": m["suggested_statement"],
                "suggested_fields": None,
            })
        obj = json.loads(u.model_dump_json())
        obj["mb_txn_usage"] = metadata  # keep same key for output compatibility
        results.append(obj)
    return results
