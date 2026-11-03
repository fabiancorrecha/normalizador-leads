"""La carga de secretos locales (`.env`): solo pasa al entorno lo que falta, y nunca lo muestra."""

import os

from normalizador.cli import cargar_secretos_locales


def test_carga_las_variables_que_faltan_y_respeta_las_que_ya_estan(tmp_path, monkeypatch):
    archivo = tmp_path / "secretos"
    archivo.write_text(
        "# comentario\n\nPRUEBA_UNA='con comillas'\nPRUEBA_DOS=\"dobles\" \n"
        "PRUEBA_YA=nuevo\nsin_igual\n=sin_nombre\nPRUEBA_VACIA=\n",
        encoding="utf-8",
    )
    for nombre in ("PRUEBA_UNA", "PRUEBA_DOS", "PRUEBA_VACIA"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("PRUEBA_YA", "anterior")

    cargar_secretos_locales(archivo)

    assert os.environ["PRUEBA_UNA"] == "con comillas"
    assert os.environ["PRUEBA_DOS"] == "dobles"
    assert os.environ["PRUEBA_YA"] == "anterior"  # el entorno manda sobre el archivo
    assert "PRUEBA_VACIA" not in os.environ


def test_sin_archivo_no_pasa_nada(tmp_path):
    cargar_secretos_locales(tmp_path / "no_existe")
