import json
from pymongo import MongoClient

# Check what was actually extracted for this document
client = MongoClient('mongodb+srv://ritam:ritam%40123@cluster0.r7q0g.mongodb.net/?retryWrites=true&w=majority')
db = client['lextrace']
extractions = db['extractions']

doc = extractions.find_one({'document_id': 'doc_4b1bb7b3'})
if doc:
    print('Found extraction:')
    if 'Extraction' in doc and 'Key_Directions' in doc['Extraction']:
        for i, directive in enumerate(doc['Extraction']['Key_Directions'][:3]):
            print(f'{i+1}. {directive}')
    print(f'\nExtraction method: {doc.get("extraction_method", "unknown")}')
    print(f'RAG Source Pages: {doc.get("RAG_Source_Pages", [])}')
else:
    print('Document not found in extractions')
