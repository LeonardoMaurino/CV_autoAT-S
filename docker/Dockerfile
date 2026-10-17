# Runner do n8n com bibliotecas extras de Python (pandas + matplotlib, usadas no relatório semanal).
# A versão da imagem base TEM que ser a mesma do n8n (n8nio/n8n:2.9.4 no docker-compose.yml).
FROM n8nio/runners:2.9.4

USER root
RUN cd /opt/runners/task-runner-python \
 && uv pip install pandas matplotlib \
 && mkdir -p /opt/runners/mplconfig \
 && chown runner /opt/runners/mplconfig
USER runner

# Gera o cache de fontes do matplotlib já na imagem (senão o primeiro gráfico demora bem mais)
RUN MPLCONFIGDIR=/opt/runners/mplconfig /opt/runners/task-runner-python/.venv/bin/python \
      -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot"
