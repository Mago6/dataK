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

Lo primero que se tomó en cuenta fue el análisis de los datos. Procuré el uso de Python porque, al abrir Excel, los carga de manera rápida, leyendo los 3500 registros y pudiendo trabajar la información en bruto. La programación fue con ayuda de DeepSeek, ya que se cuentan con los conocimientos para construir este código a mano sin la IA, pero tardaría 5 veces el tiempo tomado en programar debido a la gran cantidad de cambios.

Una vez cargados los datos, se le solicitó la creación de gráficas para entender los datos y saber cómo se veían. Partiendo de ahí, se pudo analizar cómo las variables X, Y, Z afectaban los costos, teniendo en cuenta primero las instrucciones y después variando los datos para determinar si existía alguna otra variable que afectara los resultados, por lo que se determinó otro modelo, el modelo propio. Al realizar estos análisis y con la ayuda de Python, se pudo ir observando cómo las gráficas empataban con los datos de histórico que se tenían. Esto primero para entender el caso de predicción de costos, con volatilidad de mercado.

## 2. Supuestos

Empezamos trabajando con las instrucciones del caso, pero al ver que las gráficas de histórico y las del modelo que nos decía no empataban, se cambió la fórmula para poder trabajar con más variables, para poder determinar si le afectaban, y llegamos a un modelo alternativo X + Y, con el cual empezamos a notar la gráfica más apegada y con esto nos enfocamos en solucionar el caso sin tomar solamente en cuenta Z, sino variando datos.

## 3. Formas para resolver el caso y la opción tomada en esta prueba

Una vez que teníamos un panorama general, nos dimos a la tarea de subdividir el total de los datos en dos para corroborar cuál modelo se apegaba más a los datos con los que ya se contaba de la mitad correcta del histórico, teniendo como éxito el de X + Y. Con esto se procedió a realizar pruebas de predicción futura donde, con MM3, obteníamos una línea apegada a los costos reales de equipo 1 y equipo 2 del histórico de equipos, pero muy lineal. Seguimos analizando hasta ver la variabilidad por día; nos dimos cuenta de que entre fechas había cambios drásticos de 56 a 62, por poner un ejemplo, con lo que decidimos imitar ese comportamiento para darle un sentido más real a los datos en la simulación. Con esto se procedió a calcular con Monte Carlo y de ahí simular datos reales con una variación de IC del 95 % para determinar un rango aceptable de costos que no variara mucho en error, teniendo en cuenta cambios día a día. Ya cuando se montó el modelo de IA, utilizaba la proyección de las noticias para dar valores más reales a X, Y y Z, para poder determinar costos más apegados a las noticias, determinando el mismo agente de IA X para el acero, etc.

## 4. Resultados del análisis de los datos y los modelos

Cuando notamos gráficas similares, analizamos datos proyectados a futuro de 30 días y finalmente fuimos comparando la información con el histórico de equipos para ver cuánto empataban. Vimos cómo cada modelo nos representaba líneas diferentes sobre las gráficas en el dashboard, lo que nos permitió entender lo que más se apegaba a una proyección de datos a futuro con Monte Carlo: el modelo X + Y para equipo 1 + la influencia del agente sobre X y Z. Con esto se determinó que no solo lo afectaba Z y que el modelo X + Y era mejor en R² = 0.9947.

## 5. Proyección de costos y horizonte de predicción

Se determinó que se pueden determinar costos de hasta 5 años con el modelo propio, más el análisis de los registros de histórico, así como el de Monte Carlo. Pero cuando se analizó con el agente, este determinó que las variables X y Z cambiaban según la realidad de lo que pudo haber ocurrido, como una guerra, lo cual determina los picos en las gráficas del histórico de equipos real. Esto determina que podemos imitar el comportamiento de esos datos con el modelo, pero para predecir algo más apegado a la realidad es necesario el cuestionamiento día a día del agente para que cambie los índices X y Z conforme a los datos que determinemos: acero, cobre, aluminio, etc. Esto le dará más veracidad a los datos. El horizonte lo pondría a 30 días; después de eso, es necesario alimentar de datos.

## 6. Futuros ajustes o mejoras

Teniendo en cuenta que cada día a día de futuro puede variar mucho, el agente determina por noticias del día, pero si ampliara la búsqueda de los eventos que afectan la realidad, sería más preciso si buscara noticias para cambiar valores. También añadiría una ejecución en tiempo real para que se vea cómo van cambiando los datos, ingresando históricos de equipos o archivos de datos de X, Y y Z de años venideros para determinar cómo se van actualizando los índices de error y margen R², para poder generar datos a futuro más precisos. Esto, sumado a la actualización constante del agente, podría hacer datos más verosímiles.

## 7. Apreciaciones y comentarios del caso (opcional)

Hay que entender la diferencia entre sistema experto, algoritmo evolutivo, IA y agente para poder entender por qué esto podría solucionarse sin llegar a usar de manera tan sencilla la IA, teniendo modelos más fuertes sin consumo de tokens.
