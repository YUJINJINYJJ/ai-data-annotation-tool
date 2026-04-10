import csv
from io import StringIO, BytesIO

def create_csv_in_memory(headers, rows):
    """内存生成CSV，Excel打开不乱码"""
    string_buffer = StringIO()
    writer = csv.writer(string_buffer)
    if headers:
        writer.writerow(headers)
    writer.writerows(rows)
    csv_content = string_buffer.getvalue()
    csv_bytes = b'\xef\xbb\xbf' + csv_content.encode('utf-8')
    output = BytesIO(csv_bytes)
    output.seek(0)
    return output

def create_dict_csv_in_memory(headers, dict_rows):
    """生成字典格式CSV"""
    string_buffer = StringIO()
    writer = csv.DictWriter(string_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(dict_rows)
    csv_content = string_buffer.getvalue()
    csv_bytes = b'\xef\xbb\xbf' + csv_content.encode('utf-8')
    output = BytesIO(csv_bytes)
    output.seek(0)
    return output