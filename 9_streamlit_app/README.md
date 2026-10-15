# Streamlit app: explore the evidence

A small app on top of the tested marts in BigQuery. Its tabs follow the slides: which kind, what goes wrong, my plan,
Amazon 2026, and one tab about the data. It only reads the marts and adds no rules, so the numbers are the ones the
pipeline produced. The one exception, the rating of 26 matched products a year ago, is marked on the Amazon 2026 tab.

Files: `app.py`, `requirements.txt`, `Dockerfile` (Cloud Run needs port 8080).

## Run it locally

```bash
cd 9_streamlit_app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT='<project id that holds the project2_* datasets>'
streamlit run app.py
```

## Deploy to Cloud Run

I followed the layout of Google's sample
[gemini-streamlit-cloudrun](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/sample-apps/gemini-streamlit-cloudrun):
a Dockerfile that starts Streamlit on port 8080, deployed from source.

In Cloud Shell (or any terminal with `gcloud`), from this folder:

```bash
export GOOGLE_CLOUD_PROJECT='<project id>'
export GOOGLE_CLOUD_REGION='us-central1'
export SERVICE_NAME='flower-toy-evidence'

# once per project
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com \
  --project=$GOOGLE_CLOUD_PROJECT

gcloud run deploy "$SERVICE_NAME" \
  --port=8080 \
  --source=. \
  --allow-unauthenticated \
  --region=$GOOGLE_CLOUD_REGION \
  --project=$GOOGLE_CLOUD_PROJECT \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT
```

The command prints the URL of the service when it finishes. Mine is https://flower-toy-evidence-839927014785.us-central1.run.app
(I added `--max-instances=2` to keep the cost bounded).

The app reads BigQuery as the service account of the Cloud Run service (by default the Compute Engine default
service account). It needs two roles on the project: **BigQuery Data Viewer** and **BigQuery Job User**.
If the app shows a permission error, grant them:

```bash
SA=$(gcloud run services describe "$SERVICE_NAME" --region=$GOOGLE_CLOUD_REGION --project=$GOOGLE_CLOUD_PROJECT \
  --format='value(spec.template.spec.serviceAccountName)')
for ROLE in roles/bigquery.dataViewer roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT --member="serviceAccount:$SA" --role=$ROLE
done
```

The same can be done in the Google Cloud console: Cloud Run, Create service, "Continuously deploy from a repository"
or upload the source, container port 8080, allow unauthenticated invocations, and add the variable `GOOGLE_CLOUD_PROJECT`.

## Cost

Each query is limited to 1 GB scanned and results are cached for an hour. The marts are small, so a full page load
scans a few megabytes. Cloud Run scales to zero when nobody uses the app.
