from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, Response
import os
import tempfile
from datetime import datetime
from bson.objectid import ObjectId
import logging
import mimetypes

# Importar las clases que proporcionaste
from database import MongoDBHandler
from email_sender import EmailSender
from config import MONGO_URI, DB_NAME, COLLECTION_NAME, SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')

# Inicializar conexión a MongoDB
db_handler = MongoDBHandler(
  uri=MONGO_URI,
  db_name=DB_NAME,
  collection_name=COLLECTION_NAME
)

# Inicializar servicio de email
email_sender = EmailSender(
  smtp_server=SMTP_SERVER,
  port=SMTP_PORT,
  email=EMAIL_USER,
  password=EMAIL_PASSWORD
)

# Ruta principal
@app.route('/')
def index():
  return app.send_static_file('index.html')

# Ruta para la página de documentos
@app.route('/documents.html')
def documents_page():
  return app.send_static_file('documents.html')

# API para subir documentos
@app.route('/upload', methods=['POST'])
def upload_document():
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
          
      # Obtener datos del formulario
      file = request.files.get('file')
      email = request.form.get('email')
      status = request.form.get('status')
      observations = request.form.get('observations', '')
      
      if not file or not email or not status:
          return jsonify({'success': False, 'error': 'Faltan campos requeridos'}), 400
      
      # Leer el archivo
      file_data = file.read()
      file_name = file.filename
      
      # Crear documento para MongoDB
      document = {
          "nombre_archivo": file_name,
          "archivo": file_data,
          "email": email,
          "estado": status,
          "observaciones": observations if status == 'Inválida' else 'Ninguna',
          "fecha_subida": datetime.now()
      }
      
      # Insertar en la base de datos
      doc_id = db_handler.insert_document(document)
      
      # Variable para rastrear si el email se envió correctamente
      email_enviado = False
      
      # Enviar email de confirmación
      try:
          subject = f"Factura recibida: {file_name}"
          body = f"""
          <html>
          <head>
            <meta charset="UTF-8">
            <style>
              body {{
                margin: 0;
                padding: 0;
                background-color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
              }}
              .container {{
                width: 600px;
                margin: 0 auto;
                border: 1px solid #eaeaea;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
              }}
              .header {{
                background-color: #fc0;
                padding: 30px;
                text-align: center;
              }}
              .header h1 {{
                color: #d00;
                margin: 0;
                font-size: 26px;
              }}
              .content {{
                padding: 30px;
                color: #333333;
                font-size: 16px;
                line-height: 1.6;
              }}
              .content h2 {{
                font-size: 20px;
                margin-bottom: 20px;
              }}
              .card {{
                border: 1px solid #eaeaea;
                border-radius: 6px;
                padding: 20px;
                margin-bottom: 20px;
              }}
              .card table {{
                width: 100%;
              }}
              .card td {{
                padding: 5px 0;
              }}
              .card .label {{
                font-weight: bold;
                width: 35%;
              }}
              .footer {{
                background-color: #f8f9fa;
                padding: 20px;
                text-align: center;
                font-size: 14px;
                color: #777777;
              }}
              .footer a {{
                color: #d00;
                text-decoration: none;
              }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h1>Facturación de Transportes</h1>
              </div>
              <div class="content">
                <h2>Estimado/a Cliente,</h2>
                <p>Hemos recibido su factura <strong>{file_name}</strong>.</p>
                <div class="card">
                  <table>
                    <tr>
                      <td class="label">Estado:</td>
                      <td>{status}</td>
                    </tr>
                    <tr>
                      <td class="label">Observaciones:</td>
                      <td>{observations if observations else 'Ninguna'}</td>
                    </tr>
                    <tr>
                      <td class="label">Fecha de Recepción:</td>
                      <td>{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}</td>
                    </tr>
                  </table>
                </div>
                <p>Si tiene alguna duda o requiere asistencia, por favor contáctenos.</p>
                <p>Atentamente,<br><strong>Equipo de Facturación</strong></p>
              </div>
              <div class="footer">
                &copy; Facturación {datetime.now().year}. Todos los derechos reservados.<br>
                <a href="https://www.dhl.com/co-es/home.html">Visite nuestro sitio</a>
              </div>
            </div>
          </body>
          </html>
          """
          
          # Usar directamente el método send_email_with_binary para evitar crear archivos temporales
          email_sender.send_email_with_binary(email, subject, body, file_data, file_name, is_html=True)
          
          # Marcar que el email se envió correctamente
          email_enviado = True
          
          logger.info(f"Email de confirmación enviado a {email} con archivo adjunto: {file_name}")
      except Exception as e:
          logger.error(f"Error enviando email de confirmación: {str(e)}")
          # No fallamos la operación completa si el email falla
          email_enviado = False
      
      # Actualizar el estado de envío del correo en la base de datos
      try:
          db_handler.update_email_status(doc_id, email_enviado)
      except Exception as e:
          logger.error(f"Error actualizando estado de envío de correo: {str(e)}")
      
      return jsonify({'success': True, 'doc_id': doc_id})
  
  except Exception as e:
      logger.error(f"Error al subir documento: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500

# API para obtener documentos
@app.route('/documents', methods=['GET'])
def get_documents():
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
          
      documents = db_handler.get_all_documents()
      
      # Convertir ObjectId a string para serialización JSON
      for doc in documents:
          doc['_id'] = str(doc['_id'])
          # No enviar el archivo binario en la lista
          if 'archivo' in doc:
              del doc['archivo']
      
      return jsonify({'success': True, 'documents': documents})
  
  except Exception as e:
      logger.error(f"Error al obtener documentos: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500

# API para descargar documento
@app.route('/download', methods=['POST'])
def download_document():
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
          
      doc_id = request.form.get('doc_id')
      
      if not doc_id:
          return jsonify({'success': False, 'error': 'ID de documento no proporcionado'}), 400
      
      # Obtener documento por ID
      document = db_handler.get_document_by_id(doc_id)
      
      if not document:
          return jsonify({'success': False, 'error': 'Documento no encontrado'}), 404
      
      # Crear archivo temporal
      temp_file = tempfile.NamedTemporaryFile(delete=False)
      temp_file.write(document['archivo'])
      temp_file.close()
      
      # Enviar archivo
      return send_file(
          temp_file.name,
          as_attachment=True,
          download_name=document['nombre_archivo'],
          mimetype='application/octet-stream'
      )
  
  except Exception as e:
      logger.error(f"Error al descargar documento: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500
  
  finally:
      # Limpiar archivo temporal
      if 'temp_file' in locals():
          os.unlink(temp_file.name)

# API para visualizar documento
@app.route('/view-document/<doc_id>', methods=['GET'])
def view_document(doc_id):
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
      
      # Obtener documento por ID
      document = db_handler.get_document_by_id(doc_id)
      
      if not document:
          return jsonify({'success': False, 'error': 'Documento no encontrado'}), 404
      
      # Determinar el tipo MIME basado en la extensión del archivo
      file_name = document['nombre_archivo']
      file_ext = os.path.splitext(file_name)[1].lower()
      
      mime_type = mimetypes.guess_type(file_name)[0]
      if not mime_type:
          # Valores predeterminados por extensión
          if file_ext in ['.pdf']:
              mime_type = 'application/pdf'
          elif file_ext in ['.jpg', '.jpeg']:
              mime_type = 'image/jpeg'
          elif file_ext in ['.png']:
              mime_type = 'image/png'
          else:
              mime_type = 'application/octet-stream'
      
      # Devolver el archivo para visualización en el navegador
      return Response(
          document['archivo'],
          mimetype=mime_type,
          headers={
              "Content-Disposition": f"inline; filename={file_name}",
              "Content-Type": mime_type
          }
      )
  
  except Exception as e:
      logger.error(f"Error al visualizar documento: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500

# API para actualizar estado
@app.route('/update-status', methods=['POST'])
def update_status():
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
          
      data = request.json
      doc_id = data.get('doc_id')
      status = data.get('status')
      observations = data.get('observations', '')
      
      if not doc_id or not status:
          return jsonify({'success': False, 'error': 'Faltan campos requeridos'}), 400
      
      # Actualizar estado en la base de datos
      db_handler.update_document_status(doc_id, status, observations)
      
      # Obtener el documento actualizado
      document = db_handler.get_document_by_id(doc_id)
      
      # Variable para rastrear si el email se envió correctamente
      email_enviado = False
      
      # Enviar email de notificación
      try:
          email_to = document.get('email')
          file_name = document.get('nombre_archivo')
          if email_to and file_name:
              subject = f"Actualización de estado: {file_name}"
              body = f"""
              <html>
              <head>
                <meta charset="UTF-8">
                <style>
                  body {{
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff;
                    font-family: 'Segoe UI', sans-serif;
                  }}
                  .container {{
                    width: 600px;
                    margin: 0 auto;
                    border: 1px solid #eaeaea;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                  }}
                  .header {{
                    background-color: #fc0;
                    padding: 30px;
                    text-align: center;
                  }}
                  .header h1 {{
                    color: #d00;
                    margin: 0;
                    font-size: 26px;
                  }}
                  .content {{
                    padding: 30px;
                    color: #333333;
                    font-size: 16px;
                    line-height: 1.6;
                  }}
                  .content h2 {{
                    font-size: 20px;
                    margin-bottom: 20px;
                  }}
                  .card {{
                    border: 1px solid #eaeaea;
                    border-radius: 6px;
                    padding: 20px;
                    margin-bottom: 20px;
                  }}
                  .card table {{
                    width: 100%;
                  }}
                  .card td {{
                    padding: 5px 0;
                  }}
                  .card .label {{
                    font-weight: bold;
                    width: 35%;
                  }}
                  .footer {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    font-size: 14px;
                    color: #777777;
                  }}
                  .footer a {{
                    color: #d00;
                    text-decoration: none;
                  }}
                </style>
              </head>
              <body>
                <div class="container">
                  <div class="header">
                    <h1>Facturación de Transportes</h1>
                  </div>
                  <div class="content">
                    <h2>Estimado/a Cliente,</h2>
                    <p>Le informamos el estado actualizado de su factura <strong>{file_name}</strong>.</p>
                    <div class="card">
                      <table>
                        <tr>
                          <td class="label">Estado:</td>
                          <td>{status}</td>
                        </tr>
                        <tr>
                          <td class="label">Observaciones:</td>
                          <td>{observations if observations else 'Ninguna'}</td>
                        </tr>
                        <tr>
                          <td class="label">Fecha de Actualización:</td>
                          <td>{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}</td>
                        </tr>
                      </table>
                    </div>
                    <p>Si tiene alguna duda o requiere asistencia, por favor contáctenos.</p>
                    <p>Atentamente,<br><strong>Equipo de Facturación</strong></p>
                  </div>
                  <div class="footer">
                    &copy; Facturación {datetime.now().year}. Todos los derechos reservados.<br>
                    <a href="https://www.dhl.com/co-es/home.html">Visite nuestro sitio</a>
                  </div>
                </div>
              </body>
              </html>
              """
              
              # Usar directamente el método send_email_with_binary para evitar crear archivos temporales
              if 'archivo' in document:
                  email_sender.send_email_with_binary(email_to, subject, body, document['archivo'], file_name, is_html=True)
                  email_enviado = True
                  logger.info(f"Email de actualización enviado a {email_to} con archivo adjunto: {file_name}")
              else:
                  email_enviado = False
                  logger.error(f"No se encontró el archivo para el documento {doc_id}")
      except Exception as e:
          logger.error(f"Error enviando email de actualización: {str(e)}")
          # No fallamos la operación completa si el email falla
          email_enviado = False
      
      # Actualizar el estado de envío del correo en la base de datos
      try:
          db_handler.update_email_status(doc_id, email_enviado)
      except Exception as e:
          logger.error(f"Error actualizando estado de envío de correo: {str(e)}")
      
      return jsonify({'success': True})
  
  except Exception as e:
      logger.error(f"Error al actualizar estado: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500

# API para eliminar documento
@app.route('/delete-document', methods=['POST'])
def delete_document():
  try:
      # Conectar a la base de datos si es necesario
      if db_handler.collection is None:
          db_handler.connect()
          
      data = request.json
      doc_id = data.get('doc_id')
      
      if not doc_id:
          return jsonify({'success': False, 'error': 'ID de documento no proporcionado'}), 400
      
      # Eliminar documento de la base de datos
      db_handler.delete_document(doc_id)
      
      return jsonify({'success': True})
  
  except ValueError as e:
      logger.error(f"Error al eliminar documento: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 404
  
  except Exception as e:
      logger.error(f"Error al eliminar documento: {str(e)}")
      return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
  # Conectar a la base de datos al iniciar la aplicación
  try:
      db_handler.connect()
  except Exception as e:
      logger.error(f"Error al conectar a la base de datos: {str(e)}")
  
  app.run(host='0.0.0.0', port=5000)
