import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "precision-medicine-toolbox"))

import numpy as np
from pymongo import MongoClient
from pmtool.ToolBox import ToolBox

from modules.nodule_features import get_all_features


def get_folder_paths(cnp):
    static_directory = os.environ.get("STATIC_DATA_PATH", "/app/static")
    cnp_directory = os.path.join(static_directory, cnp)
    converted_nrrds_folder = os.path.join(cnp_directory, "converted_nrrds")
    dcm_path = os.path.join(cnp_directory, "dcms")
    return cnp_directory, converted_nrrds_folder, dcm_path


def get_subdirectories(folder):
    if not os.path.isdir(folder):
        return []
    return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 dicom_converter.py PACIENT_CNP", file=sys.stderr)
        sys.exit(1)

    pacient_cnp = sys.argv[1]
    mongo_connection_string = os.environ.get("MONGO_CONNECTION_STRING", "").strip()
    if not mongo_connection_string:
        print("MONGO_CONNECTION_STRING is not set", file=sys.stderr)
        sys.exit(1)

    path_to_data, converted_nrrds_folder, dcm_path = get_folder_paths(pacient_cnp)
    if not os.path.isdir(dcm_path):
        print(f"No DICOM folder found at {dcm_path}", file=sys.stderr)
        sys.exit(1)

    parameters = {
        "data_path": dcm_path,
        "data_type": "dcm",
        "multi_rts_per_pat": True,
    }

    data_ct = ToolBox(**parameters)
    data_ct.convert_to_nrrd(path_to_data, "gtv")

    data_ct_nrrd = ToolBox(converted_nrrds_folder, data_type="nrrd")
    data_ct_nrrd.get_jpegs(path_to_data)

    subdirectories = get_subdirectories(converted_nrrds_folder)
    if not subdirectories:
        print(f"No converted NRRD scans found in {converted_nrrds_folder}", file=sys.stderr)
        sys.exit(1)

    (
        nodule_volume,
        nodule_fractal_dimension,
        nodule_area,
        calcification,
        spiculation,
        type_of_nodule,
    ) = get_all_features(converted_nrrds_folder, subdirectories)

    data = []
    for i, _selected_folder in enumerate(subdirectories):
        data.append(
            {
                "nodule_volume": nodule_volume[i],
                "nodule_area": nodule_area[i],
                "fractal_dimension": nodule_fractal_dimension[i],
                "calcification": calcification[i].tolist()
                if isinstance(calcification[i], np.ndarray)
                else calcification[i],
                "spiculation": spiculation[i].tolist()
                if isinstance(spiculation[i], np.ndarray)
                else spiculation[i],
                "type_of_nodule": type_of_nodule[i],
            }
        )

    client = MongoClient(mongo_connection_string)
    db = client.get_default_database()
    db.patients.update_one({"cnp": pacient_cnp}, {"$set": {"Data": data}}, upsert=True)
    print(f"Converted and stored features for CNP {pacient_cnp}")


if __name__ == "__main__":
    main()
