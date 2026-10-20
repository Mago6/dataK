# Proyecto: Gestión de Costos Operativos

Este repositorio contiene el código para el análisis, modelado y proyección de costos de equipos, junto con un Agente de IA integrado para la interpretación de noticias macroeconómicas.

## Requisitos previos
- Python 3.9 o superior.
- Una API Key gratuita de [Groq](https://console.groq.com/).

## Instalación

1. Clona este repositorio en tu computadora.
2. Instala las dependencias ejecutando en la terminal:
   ```bash
   pip install -r requirements.txt
3.Prepara los datos:
Al ejecutar el script, se creará automáticamente una carpeta llamada dn. Debes colocar tu archivo de datos llamado historico_equipos.xlsx dentro de esa carpeta.


## Informe con los siguientes títulos:
## 1. Explicación del caso
Lo primero que se tomo en cuenta fue el analisis de los datos, procure el uso de python por que al abrir excel los carga de manera rápida 
leyendo los 3500 registros y pudiendo trabajar la información en bruto, la programación fue con ayuda de deepseek ya que se cuentan con los 
conocimientos para construir este código a mano sin la IA pero tardaría 5 veces el tiempo programando debido a la gran cantidad de cambios,
una vez cargados los datos se le solicito la creación de graficas para entender los datos y saber como se veian, partiendo de ahí 
se pudo analizar como las variables x y z afectaban los costos, teniendo en cuenta primero las instrucciones y despues variando los datos 
para determinar si existia alguna otra variable que afectara los resultados por lo que se determino otro modelo, el modelo propio, al realizar 
estos analisis y con la ayuda de python se pudo ir observando como las graficas empataban con los datos de historico que se tenian esto primero 
para entender el caso de predicción de costos, con volatibilidad de mercado.
## 2. Supuestos
Empezamos trabajando con las instrucciones del caso pero al ver que las graficas de historico y las del modelo que nos decia no empataban, se
cambio la formula para poder trabajar con mas variables y determinar si le afectaban y determinamos un modelo alternativo X + Y con el cual empezamos
a notar la grafica mas apegada y con esto nos apegamos a pensar en solucionar el caso sin tomar en cuenta z solamente variando datos.
## 3. Formas para resolver el caso y la opción tomada en esta prueba
Una vez que teniamos un panorama general nos dimos a la tarea de subdividir el total de los datos en dos para corroborar cual modelo se apegaba más
teniendo como exito el de x + y con esto se procedio a realizar pruebas de predicción futura donde con MM3 obteniamos una linea apegada a los costos de
equipo1 y equipo2 reales del historico de equipos, pero muy lineal, seguimos analizando hasta ver la variabilidad por dia entre fechas cambiando drastico 
de 56 a 62 por poner un ejemplo con lo que decidimos, imitar ese comportamiento para darle un sentido mas real a los datos en la simulacion con lo que se 
procedio, a calcular monte carlo y de ahí partir de datos reales con una variacion de IC del 95% para determinar un rango aceptable de costos que no variara
en error mucho, teniendo en cuenta cambios dia a dia, ya cuando se monto el modelo de IA utilizaba la proyeccion de las noticias para dar valores mas reales a 
x, y, y z para poder determinar costos mas reales con las noticias, determinando el mismo x para el acero, etc,.

## 4. Resultados del análisis de los datos y los modelos
## 5. Proyección de costos y horizonte de predicción
## 6. Futuros ajustes o mejoras
## 7. Apreciaciones y comentarios del caso (opcional)
