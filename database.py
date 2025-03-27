import certifi
from pymongo import MongoClient
from bson.binary import Binary
from bson.objectid import ObjectId
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

class MongoDBHandler:
    """Manejador de operaciones con MongoDB Atlas"""
    
    def __init__(self, uri: str, db_name: str, collection_name: str):
        self.uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client: Optional[MongoClient] = None
        self.collection = None

    def connect(self) -> None:
        """Establece conexión segura con MongoDB Atlas"""
        try:
            # Usar tlsCAFile solo si la URI es para MongoDB Atlas (contiene mongodb+srv)
            if "mongodb+srv" in self.uri:
                self.client = MongoClient(
                    self.uri,
                    tls=True,
                    tlsCAFile=certifi.where()
                )
            else:
                self.client = MongoClient(self.uri)
                
            db = self.client[self.db_name]
            self.collection = db[self.collection_name]
            
            # Test de conexión con manejo de errores detallado
            ping_result = self.client.admin.command('ping')
            if ping_result.get('ok') != 1.0:
                raise ConnectionError("Fallo en la verificación de conexión")
                
            logging.info("Conexión a MongoDB Atlas establecida correctamente")
            
        except Exception as e:
            logging.error(f"Error de conexión: {str(e)}")
            self.collection = None
            raise ConnectionError(f"No se pudo conectar a MongoDB: {str(e)}")

    def disconnect(self) -> None:
        """Cierra la conexión con MongoDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.collection = None
            logging.info("Conexión a MongoDB cerrada")

    def insert_document(self, document: Dict[str, Any]) -> str:
        """Inserta un documento en la colección"""
        if self.collection is None:
            self.connect()
            
        try:
            # Asegurarse de que el archivo sea binario
            if 'archivo' in document and not isinstance(document['archivo'], Binary):
                document['archivo'] = Binary(document['archivo'])
                
            document_con_fechas = {
                **document,
                "fecha": datetime.utcnow(),
                "fecha_actualizacion": datetime.utcnow()
            }
            
            result = self.collection.insert_one(document_con_fechas)
            logging.info(f"Documento insertado ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error insertando documento: {str(e)}")
            raise

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Obtiene todos los documentos con zona horaria local"""
        if self.collection is None:
            self.connect()
            
        try:
            pipeline = [
                {
                    "$addFields": {
                        "fecha_local": {
                            "$dateToString": {
                                "format": "%Y-%m-%d %H:%M:%S",
                                "date": "$fecha",
                                "timezone": "America/Bogota"
                            }
                        }
                    }
                }
            ]
            
            return list(self.collection.aggregate(pipeline))
            
        except Exception as e:
            logging.error(f"Error obteniendo documentos: {str(e)}")
            raise

    def get_document_by_id(self, doc_id: str) -> Dict[str, Any]:
        """Obtiene un documento por su ID"""
        if self.collection is None:
            self.connect()
            
        try:
            document = self.collection.find_one({"_id": ObjectId(doc_id)})
            
            if not document:
                raise ValueError(f"Documento con ID {doc_id} no encontrado")
                
            return document
            
        except Exception as e:
            logging.error(f"Error obteniendo documento: {str(e)}")
            raise

    def update_document_status(self, doc_id: str, new_status: str, observaciones: str = "") -> None:
        """Actualiza el estado de un documento"""
        if self.collection is None:
            self.connect()
            
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {
                        "estado": new_status,
                        "observaciones": observaciones,
                        "fecha_actualizacion": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                raise ValueError(f"Documento con ID {doc_id} no encontrado o no modificado")
                
            logging.info(f"Documento {doc_id} actualizado correctamente")
            
        except Exception as e:
            logging.error(f"Error actualizando documento: {str(e)}")
            raise

    def update_document_name(self, doc_id: str, new_name: str) -> None:
        """Actualiza el nombre de un documento"""
        if self.collection is None:
            self.connect()
            
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {
                        "nombre_archivo": new_name,
                        "fecha_actualizacion": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                raise ValueError(f"Documento con ID {doc_id} no encontrado o no modificado")
                
            logging.info(f"Nombre del documento {doc_id} actualizado correctamente")
            
        except Exception as e:
            logging.error(f"Error actualizando nombre del documento: {str(e)}")
            raise

    def delete_document(self, doc_id: str) -> None:
        """Elimina un documento por su ID"""
        if self.collection is None:
            self.connect()
            
        try:
            result = self.collection.delete_one({"_id": ObjectId(doc_id)})
            
            if result.deleted_count == 0:
                raise ValueError(f"Documento con ID {doc_id} no encontrado")
                
            logging.info(f"Documento {doc_id} eliminado correctamente")
            
        except Exception as e:
            logging.error(f"Error eliminando documento: {str(e)}")
            raise