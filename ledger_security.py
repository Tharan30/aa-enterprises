"""Side-effect-free input and deployment configuration guards."""
from zipfile import ZipFile


def mysql_options(config):
    options = {key: config[key] for key in ('host', 'user', 'password', 'database')}
    options.update(port=int(config.get('port', 3306)), autocommit=False, connection_timeout=10)
    if config.get('ssl_disabled', False):
        if config['host'] not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Unencrypted MySQL is restricted to loopback testing.')
        options['ssl_disabled'] = True
    else:
        options.update(ssl_disabled=False, ssl_ca=config['ssl_ca'],
                       ssl_verify_cert=True, ssl_verify_identity=True)
    return options


def validate_xlsx(upload):
    """Bound both compressed input and expanded archive before invoking openpyxl."""
    upload.seek(0, 2)
    if upload.tell() > 5 * 1024 * 1024:
        raise ValueError('XLSX upload exceeds 5 MiB.')
    upload.seek(0)
    try:
        with ZipFile(upload) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(item.file_size for item in entries) > 25 * 1024 * 1024:
                raise ValueError('XLSX expanded archive exceeds safety limits.')
            if any(item.flag_bits & 1 for item in entries):
                raise ValueError('Encrypted XLSX archives are unsupported.')
            if not {'[Content_Types].xml', 'xl/workbook.xml'}.issubset(archive.namelist()):
                raise ValueError('Not an XLSX workbook.')
    finally:
        upload.seek(0)
