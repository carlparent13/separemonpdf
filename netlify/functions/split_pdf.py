import json
import base64
import io
import zipfile
import pikepdf

def handler(event, context):
    # CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": ""
        }

    try:
        body = json.loads(event.get("body", "{}"))
        pdf_b64     = body.get("pdf")
        pages_per   = int(body.get("pagesPerDoc", 1))
        title       = body.get("title", "Document")
        password    = body.get("password", "")   # empty string = no protection
        zip_name    = body.get("zipName", "documents")

        if not pdf_b64:
            return error_response("Aucun PDF fourni.", 400)
        if pages_per < 1:
            return error_response("Nombre de pages invalide.", 400)

        # Decode PDF
        pdf_bytes = base64.b64decode(pdf_b64)

        # Open source PDF
        src = pikepdf.open(io.BytesIO(pdf_bytes))
        total_pages = len(src.pages)
        total_docs  = -(-total_pages // pages_per)  # ceiling division

        # Build ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(total_docs):
                num      = str(i + 1).zfill(2)
                doc_name = f"#{num} {title}"
                file_name = f"{doc_name}.pdf"

                start = i * pages_per
                end   = min(start + pages_per, total_pages)

                # Create new PDF with selected pages
                new_pdf = pikepdf.new()
                new_pdf.pages.extend(src.pages[start:end])

                # Set metadata
                with new_pdf.open_metadata() as meta:
                    meta["dc:title"] = doc_name
                    meta["dc:creator"] = "PDF Splitter — Carl Parent"

                out_buf = io.BytesIO()

                if password:
                    # AES-256 encryption — highest level available in pikepdf
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
                        owner=password + "_owner",
                        user=password,
                        R=6,                  # Revision 6 = AES-256
                        allow=permissions,
                    )
                    new_pdf.save(out_buf, encryption=encryption)
                else:
                    new_pdf.save(out_buf)

                zf.writestr(file_name, out_buf.getvalue())

        zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")

        return {
            "statusCode": 200,
            "headers": {**cors_headers(), "Content-Type": "application/json"},
            "body": json.dumps({
                "zip": zip_b64,
                "zipName": f"{zip_name}.zip",
                "totalDocs": total_docs,
                "totalPages": total_pages,
            })
        }

    except Exception as e:
        return error_response(f"Erreur serveur : {str(e)}", 500)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

def error_response(msg, code=400):
    return {
        "statusCode": code,
        "headers": {**cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps({"error": msg})
    }
