def build_client(project_id: str):
    from google.cloud import bigquery
    return bigquery.Client(project=project_id)
