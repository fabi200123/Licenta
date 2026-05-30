import hashlib
import os
import sys

import pdfplumber
from pymongo import MongoClient

"""
How to run:
$ python3 pdf_extractor.py PACIENT_CNP PDF_FILE
"""


def split_subfields(value):
    subfields = {}
    if value.startswith("Bilirubina totala") or value.startswith("Inaltime (cm)"):
        temp_value = value.replace(". ,", "<TEMP>")
        parts = temp_value.split(", ")
        for part in parts:
            part = part.replace("<TEMP>", ". ,")
            if "=" in part:
                sf_field, sf_value = part.split("=", 1)
                subfields[sf_field.strip()] = sf_value.strip()
            else:
                subfields[part] = ""
        return subfields
    if value.startswith("["):
        value = value[1:-1]
        parts = value.split(", ")
        for part in parts:
            if "=" in part:
                sf_field, sf_value = part.split("=", 1)
                subfields[sf_field.strip()] = sf_value.strip()
            else:
                subfields[part] = ""
        return subfields
    if "," in value and "=" in value:
        parts = value.split(", ")
        for part in parts:
            if "=" in part:
                sf_field, sf_value = part.split("=", 1)
                subfields[sf_field.strip()] = sf_value.strip()
            else:
                subfields[part] = ""
        return subfields
    return value


def compute_pdf_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as pdf_file:
        for chunk in iter(lambda: pdf_file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_hemoleucograma(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()

    if not text:
        raise ValueError("Could not extract text from PDF")

    start_index = text.find("BILET DE IESIRE / SCRISOARE MEDICALA")
    if start_index == -1:
        raise ValueError("Medical report section not found in PDF")

    section_text = text[start_index:]
    lines = section_text.split("\n")

    data_dict = {}
    current_field = None
    for line in lines:
        if ":" in line:
            field, value = line.split(":", 1)
            field = field.strip()
            value = value.strip()
            current_field = field
            data_dict[field] = split_subfields(value)
        elif current_field is not None:
            subfields = split_subfields(line)
            if isinstance(subfields, dict):
                if isinstance(data_dict[current_field], dict):
                    data_dict[current_field].update(subfields)
                else:
                    data_dict[current_field] = subfields
            else:
                if isinstance(data_dict[current_field], list):
                    data_dict[current_field].append(subfields)
                else:
                    data_dict[current_field] = [data_dict[current_field], subfields]

    hemoleucograma_completa_dict = data_dict.get("Hemoleucograma completa", {})
    if not hemoleucograma_completa_dict:
        raise ValueError("Hemoleucograma completa section not found in PDF")

    buletin_key = None
    for key in data_dict:
        if "Buletin" in key:
            buletin_key = key
            break

    if not buletin_key:
        raise ValueError("Buletin date not found in PDF")

    buletin_date = buletin_key.split(" ")[1]
    hemoleucograma_completa_dict["date"] = buletin_date
    return hemoleucograma_completa_dict


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 pdf_extractor.py PACIENT_CNP PDF_FILE", file=sys.stderr)
        sys.exit(1)

    pacient_cnp = sys.argv[1]
    pdf_file = sys.argv[2]

    if not os.path.isfile(pdf_file):
        print(f"PDF file not found: {pdf_file}", file=sys.stderr)
        sys.exit(1)

    mongo_connection_string = os.environ.get("MONGO_CONNECTION_STRING", "").strip()
    if not mongo_connection_string:
        print("MONGO_CONNECTION_STRING is not set", file=sys.stderr)
        sys.exit(1)

    pdf_hash = compute_pdf_hash(pdf_file)
    hemoleucograma_completa_dict = extract_hemoleucograma(pdf_file)
    hemoleucograma_completa_dict["pdf_hash"] = pdf_hash

    client = MongoClient(mongo_connection_string)
    db = client.get_default_database()
    collection = db.patients

    patient = collection.find_one({"cnp": pacient_cnp})
    if not patient:
        print(f"Patient with CNP {pacient_cnp} not found in MongoDB", file=sys.stderr)
        sys.exit(1)

    existing_entries = patient.get("Hemoleucograma_completa") or []
    for entry in existing_entries:
        if entry.get("pdf_hash") == pdf_hash:
            print(f"SKIP_DUPLICATE: PDF already stored for CNP {pacient_cnp}")
            sys.exit(0)

    result = collection.update_one(
        {"cnp": pacient_cnp},
        {"$push": {"Hemoleucograma_completa": hemoleucograma_completa_dict}},
    )

    if result.modified_count == 0:
        print(f"Failed to store PDF data for CNP {pacient_cnp}", file=sys.stderr)
        sys.exit(1)

    print(
        f"INSERTED: Hemoleucograma for CNP {pacient_cnp}, "
        f"date {hemoleucograma_completa_dict['date']}"
    )


if __name__ == "__main__":
    main()
