# In your_app/tasks.py

from celery import shared_task
from .utils import predict_ic50  # Your ML prediction function
import requests
import pubchempy as pcp

# We move the PubChem helper methods here from the view, making them regular functions.
def fetch_pubchem_description(cid):
    """Fetch compound description from PubChem API."""
    # ... (same code as in your view)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/description/JSON"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            descriptions = json_data.get("InformationList", {}).get("Information", [])
            for item in descriptions:
                if "Description" in item:
                    return item["Description"]
    except requests.RequestException as e:
        print(f"Error fetching description from PubChem: {e}")
    return None

def fetch_pubchem_data(smiles):
    """Fetch compound data from PubChem."""
    # ... (same code as in your view, but without `self`)
    data = {"cid": None, "iupac_name": None, "molecular_formula": None, "molecular_weight": None, "structure_image": None}
    try:
        compounds = pcp.get_compounds(smiles, 'smiles')
        if compounds:
            compound = compounds[0]
            data.update({
                "cid": compound.cid, "iupac_name": compound.iupac_name,
                "molecular_formula": compound.molecular_formula, "molecular_weight": compound.molecular_weight,
                "structure_image": f"https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid={compound.cid}&t=l"
            })
            if compound.cid:
                data["description"] = fetch_pubchem_description(compound.cid)
    except Exception as e:
        print(f"Error fetching data from PubChem: {e}")
    return data

# This is our main Celery task
@shared_task
def process_single_smiles(smiles, model_name, model_method, model_descriptor):
    """
    Celery task to perform prediction and data fetching for one SMILES string.
    """
    # 1. Get predicted IC50 from your ML model
    ic50 = predict_ic50(smiles, model_name, model_method, model_descriptor)

    if ic50 is None:
        return {"smiles": smiles, "error": "Invalid SMILES string or prediction failed"}

    # 2. Fetch data from PubChem
    compound_data = fetch_pubchem_data(smiles)

    # 3. Determine activity category
    category = (
        "Highly Active" if ic50 > 8 else
        "Moderately Active" if 7 < ic50 <= 8 else
        "Weakly Active" if 6 < ic50 <= 7 else
        "Inactive"
    )

    # 4. Assemble and return the final result for this one task
    result = {
        "smiles": smiles,
        "ic50": ic50,
        "category": category,
        **compound_data  # Merge the PubChem data dictionary
    }
    return result