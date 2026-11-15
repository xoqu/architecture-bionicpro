FROM apache/airflow:2.9.3

USER root
COPY start.sh /opt/airflow/start.sh
RUN chmod 755 /opt/airflow/start.sh

USER airflow
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY dags/ /opt/airflow/dags/
