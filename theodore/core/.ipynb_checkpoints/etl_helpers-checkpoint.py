import numpy as np
import pandas as pd
import traceback
import json

from pathlib import Path
from pandas.errors import DtypeWarning, ParserError
from typing import List, Any, Tuple, Dict, Literal
from theodore.core.utils import user_info, base_logger
from theodore.core.file_helpers import resolve_path


class NumpySerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super().default(obj)
        

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected a Pandas DataFrame but got {type(df).__name__}")
    
    df.columns = (df.columns
                  .str.lower()
                  .str.strip()
                  .str.replace(r"\s+", "_")
                  .str.replace(r"[^A-Za-z0-9_]", "_", regex=True)
                )
    return df

def clean_records(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"expected a pandas DataFrame but got {type(df).__name__}")
    
    try:
        clean_col_df = clean_column_names(df)
    except ValueError:
        raise 
    try:
        obj_cols =  clean_col_df.select_dtypes('object').columns
        clean_col_df[obj_cols] = clean_col_df[obj_cols].apply(lambda x: x.str.strip())
        return clean_col_df
    except ParserError:
        raise

def get_data_profile(df: pd.DataFrame) -> Tuple[Dict[str, int | str], Dict[str, int | str]]:
    """
    Get profile about a pandas DataFrame object.
    returns a tuple of general and numeric dictionaries with columns as rows
    - General_desc [value counts, Null count, data types, null percentage (col wise)] or None if no string dtypes,
    - Numeric_desc [mean, std, outliers, null count, datatypes ] or None if no Numeric dtypes
    """
    df_cp = df.copy()
    numeric_df = df_cp.select_dtypes(include=[np.number])
    object_cols = df_cp.select_dtypes(include=["object"]).columns
    
    # 1. General Profile (Metadata)
    generalStats = {
        "row_count": df_cp.shape[0],
        "col_count": df_cp.shape[1],
        "num_count": numeric_df.shape[1],
        "obj_count": df_cp[object_cols].shape[1],
        "null_count": np.abs(df_cp.count().sum() - df_cp.shape[0] * df_cp.shape[1]),
        "unique_count": df_cp.nunique().sum(),
        "duplicated_count": df_cp.duplicated().sum()
    }

    # 2. Numeric Profile
    numero = {}

    if not numeric_df.empty:
        std = numeric_df.std()
        mean = numeric_df.mean()
        z = np.where(std > 0, (numeric_df - mean) / std, 0.0)
        outliers = (np.abs(z) >= 3).sum(axis=0)
        
        numeric_dict = {
            "columns": numeric_df.columns.tolist(),
            "mean": mean,
            "max": numeric_df.max(),
            "min": numeric_df.min(),
            "std": std,
            "outliers": outliers,
            }
        numero = pd.DataFrame(numeric_dict).to_dict(orient="list")

    return json.dumps(generalStats, cls=NumpySerializer), json.dumps(numero, cls=NumpySerializer)

    
def parse_dates(df: pd.DataFrame, date_cols, errors: str = "coerce") -> pd.DataFrame:
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors=errors)
    
    return df

def transform_data(
        *,
        path: Path | str,
        date_cols: List[str] | None = None,
        date_errors: Literal["coerce", "ignore", "raise", "RaiseCoerce"] | None = None,
        aware_datetime: bool = True,
        fillna: str | None = None,
        axis: int | None = None,
        thresh: int | None = None,
        save_to: str | Path | None= None
        ) -> Tuple[dict, dict]:
    if not isinstance(path, (Path, str)):
        raise TypeError(f"path args '{path}' not of type str or path")
    
    if not (filepath:=resolve_path(path)).exists():
        raise FileNotFoundError(f"Path {path} could not be resolved")
    
    try:
        df = pd.read_csv(filepath)
    except DtypeWarning:
        df = pd.read_csv(filepath, low_memory=False)
    except ParserError:
        raise

    df_cp = df.copy()

    if date_cols:
        if date_errors is None:
            raise ValueError("Date errors cannot be of Nonetype")
        try:
            date_df = df_cp[date_cols]
            date_df_parsed = parse_dates(date_df, date_cols=date_cols, errors=date_errors)
            df_cp[date_cols] = date_df_parsed
        except (KeyError, ParserError) as e:
            base_logger.internal(traceback.format_exc())

    
    cleaned_records = clean_records(df_cp)

    try:
        general, numeric = get_data_profile(cleaned_records)
    except TypeError:
        raise
            
    if fillna:
        try:
            df_cp.fillna(value=fillna, inplace=True)
        except (ValueError, TypeError):
            base_logger.internal(traceback.format_exc())

    try:
        if save_to:
            fullpath = str(Path(f"{save_to}/{filepath.name}"))
            cleaned_records.to_csv(fullpath)
            base_logger.internal(f"{filepath.name} saved at {fullpath}")
    except (ValueError, TypeError):
        user_info(f"Unable to save to csv: {traceback.format_exc()}")

    return general, numeric
