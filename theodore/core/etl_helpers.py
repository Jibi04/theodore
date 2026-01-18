import numpy as np
import pandas as pd
import traceback

from pathlib import Path
from pandas.errors import DtypeWarning, ParserError
from typing import List, Any, Tuple, Dict, Literal, Hashable
from theodore.core.utils import user_info


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected a Pandas DataFrame but got {type(df).__name__}")
    
    df.columns = (df.columns
                  .str.replace(r"[^A-Za-z0-9_]", "", regex=True)
                  .str.lower()
                  .str.strip()
                  .str.replace(r"\s+", "_")
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


def get_data_profile(df: pd.DataFrame) -> Tuple[Dict[Hashable, Any], Dict[Hashable, Any] | None]:
    """
    Get profile about a pandas DataFrame object.
    returns a tuple of general and numeric dictionaries with columns as rows
    - General_desc [value counts, Null count, data types, null percentage (col wise)] or None if no string dtypes,
    - Numeric_desc [mean, std, outliers, null count, datatypes ] or None if no Numeric dtypes
    """
    df_cp = df.copy()
    
    # 1. General Profile (Metadata)
    stats = {
        "Feature": df_cp.columns.tolist(),
        "Type": [str(t) for t in df_cp.dtypes],
        "Nulls": df_cp.isnull().sum().tolist(),
        "Unique": [df_cp[col].nunique() for col in df_cp.columns]
    }
    general_dict = stats

    # 2. Numeric Profile
    numeric_df = df_cp.select_dtypes(include=[np.number])
    numeric_dict = {}

    if not numeric_df.empty:
        desc = numeric_df.describe().T # Statistics as columns
        
        std = numeric_df.std()
        mean = numeric_df.mean()
        z = np.where(std > 0, (numeric_df - mean) / std, 0.0)
        outliers = (np.abs(z) >= 3).sum(axis=0)
        
        desc["outliers"] = outliers
        numeric_dict = desc.reset_index().rename(columns={"index": "Feature"}).to_dict(orient="list")

    return general_dict, numeric_dict


def transform_data(
        *,
        path: Path | str,
        date_cols: List[str] | None = None,
        date_errors: Literal["coerce", "ignore", "raise", "RaiseCoerce"],
        aware_datetime: bool = True,
        fillna: str | None = None,
        axis: int | None = None,
        thresh: int | None = None,
        save_to: str | Path | None= None
        ) -> List[Dict | None]:
    if not isinstance(path, (Path, str)):
        raise TypeError(f"path args '{path}' not of type str or path")
    
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"File to transformed not existent, not a path string or has been moved {path}.")
    
    try:
        df = pd.read_csv(filepath)
    except DtypeWarning:
        df = pd.read_csv(filepath, low_memory=False)
    except ParserError:
        raise

    df_cp = df.copy()

    if date_cols:
        for col in date_cols:
            try:
                    df_cp[col] = pd.to_datetime(df[col], errors=date_errors, utc=aware_datetime)
            except (ParserError, ValueError):
                raise
            except KeyError:
                raise KeyError(f"Unknown DataFrame column '{col}'")
    
    cleaned_records = clean_records(df_cp)

    try:
        general, numeric = get_data_profile(cleaned_records)
    except TypeError:
        raise
            
    if fillna:
        try:
            cleaned_records.fillna(axis=axis, thresh=thresh, inplace=True)
        except (ValueError, TypeError):
            raise

    try:
        if save_to:
            cleaned_records.to_csv(save_to)
    except (ValueError, TypeError):
        user_info(f"Unable to save to csv: {traceback.format_exc()}")

    return [cleaned_records.to_dict(orient="records"), general, numeric]



            
    

    
