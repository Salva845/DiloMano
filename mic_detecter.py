import os
ruta = "senas/P1_Yo.mp4"
print("Existe ruta?", os.path.isfile(ruta))
print("Ruta absoluta:", os.path.abspath(ruta))
