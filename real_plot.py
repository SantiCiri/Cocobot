import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import sqlite3
from datetime import datetime
import psycopg2

def plot_bohlinger(ratio):
    # Conectarse a la base de datos antes de realizar cualquier cálculo
    conn = psycopg2.connect(
        dbname="prices",
        user="postgres",
        password="Urbani7000",
        host="127.0.0.1"#"/var/run/postgresql"  # Usar Unix domain socket en lugar de host y puerto
    )

    # Obtener la fecha de hoy
    today_start = datetime.now().strftime('%y/%m/%d 00:00:00.000000')
    today_end = datetime.now().strftime('%y/%m/%d 23:59:59.999999')

    # Query SQL que realiza la mayoría de las transformaciones
    query = f"""
    WITH numerador AS (
        SELECT 
            timestamp, 
            DATE_TRUNC('second', timestamp) AS timestamp_s,
            precio_venta AS precio_venta_numerador
        FROM precios
        WHERE 
            short_ticker = '{ratio['numerador']['short_ticker']}' AND
            currency = '{ratio['numerador']['currency']}' AND
            term = '{ratio['numerador']['term']}' AND
            timestamp >= '{today_start}' AND 
            timestamp <= '{today_end}'
    ),
    denominador AS (
        SELECT 
            timestamp, 
            DATE_TRUNC('second', timestamp) AS timestamp_s,
            precio_compra AS precio_compra_denominador
        FROM precios
        WHERE 
            short_ticker = '{ratio['denominador']['short_ticker']}' AND
            currency = '{ratio['denominador']['currency']}' AND
            term = '{ratio['denominador']['term']}' AND
            timestamp >= '{today_start}' AND 
            timestamp <= '{today_end}'
    )
    SELECT 
        numerador.timestamp, 
        numerador.timestamp_s,
        numerador.precio_venta_numerador, 
        denominador.precio_compra_denominador,
        (numerador.precio_venta_numerador / denominador.precio_compra_denominador) AS ratio
    FROM numerador
    INNER JOIN denominador 
    ON numerador.timestamp_s = denominador.timestamp_s
    """

    # Ejecutar la query y cargar los resultados en un DataFrame de pandas
    merged_df = pd.read_sql_query(query, conn)

    # Cerrar la conexión
    conn.close()

    # Calcular la media móvil de 30 períodos
    merged_df['moving_average_30'] = merged_df['ratio'].rolling(window=30).mean()

    # Calcular la desviación estándar para la media móvil de 30 períodos
    merged_df['std_dev_30'] = merged_df['ratio'].rolling(window=30).std()

    # Calcular las Bandas de Bollinger
    merged_df['bollinger_upper'] = merged_df['moving_average_30'] + (merged_df['std_dev_30'] * 2.5)
    merged_df['bollinger_lower'] = merged_df['moving_average_30'] - (merged_df['std_dev_30'] * 2.5)
    return merged_df

# Definición del ratio
ratio={"numerador":{"short_ticker":"AL35", "currency":"ARS","term":"24hs"},
       "denominador":{"short_ticker":"AE38", "currency":"ARS","term":"24hs"}}

# Inicializar la aplicación Dash
app = dash.Dash(__name__)

# Layout de la aplicación
app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # Intervalo de actualización en milisegundos (1 segundo)
        n_intervals=0
    )
])

# Callback para actualizar el gráfico en tiempo real
@app.callback(
    Output('live-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_graph_live(n):
    # Obtener los datos actualizados
    df = plot_bohlinger(ratio=ratio)

    # Crear la figura
    fig = go.Figure()

    # Añadir la traza para el ratio
    fig.add_trace(go.Scatter(
        x=df['timestamp_s'],
        y=df['ratio'],
        mode='lines',
        name=f"Ratio {ratio['numerador']['short_ticker']}/{ratio['denominador']['short_ticker']}",
    ))

    # Añadir la traza para la media móvil de 30 períodos
    fig.add_trace(go.Scatter(
        x=df['timestamp_s'],
        y=df['moving_average_30'],
        mode='lines',
        name='Media Móvil 30 Períodos',
        line=dict(dash='dash')  # Línea discontinua para diferenciar
    ))

    # Añadir la traza para la Banda de Bollinger Superior
    fig.add_trace(go.Scatter(
        x=df['timestamp_s'],
        y=df['bollinger_upper'],
        mode='lines',
        name='Banda de Bollinger Superior',
        line=dict(color='rgba(255, 0, 0, 0.5)')  # Color rojo con opacidad
    ))

    # Añadir la traza para la Banda de Bollinger Inferior
    fig.add_trace(go.Scatter(
        x=df['timestamp_s'],
        y=df['bollinger_lower'],
        mode='lines',
        name='Banda de Bollinger Inferior',
        line=dict(color='rgba(0, 0, 255, 0.5)')  # Color azul con opacidad
    ))

    # Configurar el diseño del gráfico
    fig.update_layout(
        title=f"Ratio {ratio['numerador']['short_ticker']}/{ratio['denominador']['short_ticker']} en función del tiempo",
        xaxis_title="Tiempo",
        yaxis_title="Ratio",
        template="plotly_dark"
    )

    return fig

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run_server(debug=True)
