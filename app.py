from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import io
import zipfile
import pikepdf

app = Flask(__name__)
CORS(app)

@app.route('/split', methods=['POST', 'OPTIONS'])
def split_pdf():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json()
        pdf_b64   = data.get('pdf')
        pages_per = int(data.get('pagesPerDoc', 1))
        title     = data.get('title', 'Document')
        password  = data.get('password', '')
        zip_name  = data.get('zipName', 'documents')

        if not pdf_b64:
            return jsonify({'error': 'Aucun PDF fourni.'}), 400
        if pages_per < 1:
            return jsonify({'error': 'Nombre de pages invalide.'}), 400

        pdf_bytes = base64.b64decode(pdf_b64)
        src = pikepdf.open(io.BytesIO(pdf_bytes))
        total_pages = len(src.pages)
        total_docs  = -(-total_pages // pages_per)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i in range(total_docs):
                num       = str(i + 1).zfill(2)
                doc_name  = f'#{num} {title}'
                file_name = f'{doc_name}.pdf'

                start = i * pages_per
                end   = min(start + pages_per, total_pages)

                new_pdf = pikepdf.new()
                new_pdf.pages.extend(src.pages[start:end])

                with new_pdf.open_metadata() as meta:
                    meta['dc:title']   = doc_name
                    meta['dc:creator'] = 'PDF Splitter — Carl Parent'

                out_buf = io.BytesIO()

                if password:
                    permissions = pikepdf.Permissions(
                        accessibility=True,
                        extract=False,
                        modify_annotation=False,
                        modify_assembly=False,
                        modify_form=False,
                        modify_other=False,
                        print_lowres=True,
                        print_highres=True,
                    )
                    encryption = pikepdf.Encryption(
                        owner=password + '_owner',
                        user=password,
                        R=6,  # AES-256
                        allow=permissions,
                    )
                    new_pdf.save(out_buf, encryption=encryption)
                else:
                    new_pdf.save(out_buf)

                zf.writestr(file_name, out_buf.getvalue())

        zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')

        return jsonify({
            'zip': zip_b64,
            'zipName': f'{zip_name}.zip',
            'totalDocs': total_docs,
            'totalPages': total_pages,
        })

    except Exception as e:
        return jsonify({'error': f'Erreur serveur : {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
