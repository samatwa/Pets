# Pets

Personal applications and experiments. Coursework is maintained separately in [GoIT](https://github.com/samatwa/GoIT).

## Projects

| Area | Project | Description |
|---|---|---|
| [Streamlit](Streamlit/) | [Fjord FX](Streamlit/Fjord-FX/) | Official exchange-rate monitoring, historical charts and currency conversion |

## Run Fjord FX locally

From the repository root:

```sh
cd Streamlit/Fjord-FX
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open `http://localhost:8501`. Run from the project directory to apply its Streamlit theme.

For Streamlit Community Cloud, select `Streamlit/Fjord-FX/streamlit_app.py` as the entry point. See the [project documentation](Streamlit/Fjord-FX/) for installation, data sources, terminal commands and offline checks.

Exchange-rate caches, local databases and generated reports are created at runtime. They are excluded from this repository.
