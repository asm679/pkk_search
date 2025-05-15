import os
#os.environ['FASTKML_USE_LXML'] = '1' # Форсируем lxml
from fastkml import kml
import traceback # Убедимся, что он импортирован

kml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test</name>
    <Placemark>
      <name>P1</name>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""

# Передаем NS OGC KML 2.2
k = kml.KML(ns="http://www.opengis.net/kml/2.2")
print("KML object created with OGC NS.")
try:
    print("Attempting k.from_string()...")
    k.from_string(kml_content)
    print("from_string() called successfully.") # Эта строка теперь может не выполниться
    features = list(k.features)
    print(f"Number of features: {len(features)}")
    if features:
        print(f"First feature type: {type(features[0])}")
        if hasattr(features[0], 'name'):
            print(f"First feature name: {features[0].name}")
        
        doc_features = list(features[0].features)
        print(f"Number of features in Document: {len(doc_features)}")
        if doc_features:
            print(f"First feature in Document type: {type(doc_features[0])}")
            if hasattr(doc_features[0], 'name'):
                 print(f"First feature in Document name: {doc_features[0].name}")

except Exception as e:
    print(f"--- ERROR CAUGHT ---")
    print(f"Error type: {type(e)}")
    print(f"Error message: {e}")
    # Формируем строку с трейсбеком
    tb_str = traceback.format_exc()
    print("Traceback:")
    print(tb_str)
    print(f"--- END ERROR ---")

print("Diagnostic script finished.") 