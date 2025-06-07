from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .utils import predict_ic50
import requests
import pubchempy as pcp
from django.shortcuts import get_object_or_404
from django.db import transaction
import csv
import io
from celery import group
from .tasks import process_single_smiles # Import our new task
from celery.result import AsyncResult

# class PredictIC50View(APIView):

#     def post(self, request):
#         smiles_list = request.data.get("smiles", None)
#         model_name = request.data.get("model_name", "default_model")
#         model_method = request.data.get("model_method", "dl")
#         model_descriptor = request.data.get("model_descriptor", "ecfp")

#         results = []

#         # Step 2: Process all SMILES
#         for smiles in smiles_list:
#           ic50 = predict_ic50(smiles, model_name, model_method, model_descriptor)  # Get predicted IC50

#           if ic50 is None:
#               results.append({"smiles": smiles, "error": "Invalid SMILES string"})
#               continue  # Skip to next

#           # Fetch compound data from PubChem
#           compound_data = self.fetch_pubchem_data(smiles)

#           # Determine activity category
#           category = (
#               "Highly Active" if ic50 > 8 else
#               "Moderately Active" if 7 < ic50 <= 8 else
#               "Weakly Active" if 6 < ic50 <= 7 else
#               "Inactive"
#           )

#           results.append({
#               "iupac_name": compound_data.get("iupac_name"),
#               "smiles": smiles,
#               "cid": compound_data.get("cid"),
#               "ic50": ic50,
#               "category": category,
#               "molecular_formula": compound_data.get("molecular_formula"),
#               "molecular_weight": compound_data.get("molecular_weight"),
#               "synonyms": compound_data.get("synonyms"),
#               "inchi": compound_data.get("inchi"),
#               "inchikey": compound_data.get("inchikey"),
#               "structure_image": compound_data.get("structure_image"),
#               "description": compound_data.get("description"),
#           })

#         return Response(results, status=status.HTTP_201_CREATED)

#     def fetch_pubchem_data(self, smiles):
#         """Fetch compound data from PubChem and optimize API calls."""
#         data = {
#             "cid": None, "molecular_formula": None, "molecular_weight": None,
#             "iupac_name": None, "inchi": None, "inchikey": None, "description": None,
#             "synonyms": None, "structure_image": None, "name": None,
#             "category": None
#         }
        
#         try:
#             compounds = pcp.get_compounds(smiles, 'smiles')
#             if compounds:
#                 compound = compounds[0]  # Get the first matching compound
#                 data.update({
#                     "cid": compound.cid,
#                     "molecular_formula": compound.molecular_formula,
#                     "molecular_weight": compound.molecular_weight,
#                     "iupac_name": compound.iupac_name,
#                     "inchi": compound.inchi,
#                     "inchikey": compound.inchikey,
#                     "synonyms": ", ".join(compound.synonyms) if compound.synonyms else None,
#                     "structure_image": f"https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid={compound.cid}&t=l" if compound.cid else None,
#                 })

#                 # Fetch description from PubChem REST API
#                 if compound.cid:
#                     description = self.fetch_pubchem_description(compound.cid)
#                     if description:
#                         data["description"] = description
                        
#         except Exception as e:
#             print(f"Error fetching data from PubChem: {e}")

#         return data

#     def fetch_pubchem_description(self, cid):
#         """Fetch compound description from PubChem API."""
#         url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/description/JSON"
#         try:
#             response = requests.get(url, timeout=5)
#             if response.status_code == 200:
#                 json_data = response.json()
#                 descriptions = json_data.get("InformationList", {}).get("Information", [])
#                 for item in descriptions:
#                     if "Description" in item:
#                         return item["Description"]
#         except requests.RequestException as e:
#             print(f"Error fetching description from PubChem: {e}")
#         return None

class PredictIC50View(APIView):

    def post(self, request):
        smiles_list = request.data.get("smiles", [])
        model_name = request.data.get("model_name", "default_model")
        model_method = request.data.get("model_method", "dl")
        model_descriptor = request.data.get("model_descriptor", "ecfp")

        if not smiles_list:
            return Response({"error": "SMILES list cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a group of signature() objects for each task
        task_group = group(
            process_single_smiles.s(smiles, model_name, model_method, model_descriptor)
            for smiles in smiles_list
        )

        # Execute the group of tasks in the background
        group_result = task_group.apply_async()

        # Immediately return the task group ID to the client
        return Response(
            {"task_id": group_result.id},
            status=status.HTTP_202_ACCEPTED
        )
    
class TaskResultView(APIView):
    def get(self, request, task_id):
        # Check the result of a task group by its ID
        result = AsyncResult(task_id)

        if not result.ready():
            # If the tasks are not finished, report the status
            return Response(
                {"status": result.state, "info": result.info}, # .info can show progress
                status=status.HTTP_200_OK
            )

        # If the tasks are finished, get the results
        # Use result.get() with propagate=False to prevent raising exceptions in the view
        task_results = result.get(propagate=False)

        # Check if any individual tasks failed
        if result.failed():
             # Handle the case where the group itself failed
             return Response({"status": "FAILED", "results": str(task_results)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {"status": result.state, "results": task_results},
            status=status.HTTP_200_OK
        )