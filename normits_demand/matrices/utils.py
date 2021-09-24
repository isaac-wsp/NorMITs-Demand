# -*- coding: utf-8 -*-
"""
Created on: Tues March 2 12:21:12 2021
Updated on:

Original author: Ben Taylor
Last update made by:
Other updates made by:

File purpose:
Utility functions specific to matrices
"""
# builtins
import operator

from typing import Any
from typing import List
from typing import Union
from typing import Callable

# Third Party
import pandas as pd
import numpy as np

# Local imports


def get_wide_mask(df: pd.DataFrame,
                  zones: List[Any] = None,
                  col_zones: List[Any] = None,
                  index_zones: List[Any] = None,
                  join_fn: Callable = operator.and_
                  ) -> np.ndarray:
    """
    Generates a mask for a wide matrix. Returned mask will be same shape as df

    The zones the set the mask for can be set individually with col_zones and
    index_zones, or to the same value with zones.


    Parameters
    ----------
    df:
        The dataframe to generate the mask for

    zones:
        The zones to match to in both the columns and index. If this value
        is set it will overwrite anything passed into col_zones and
        index_zones.

    col_zones:
        The zones to match to in the columns. This value is ignored if
        zones is set.

    index_zones:
        The zones to match to in the index. This value is ignored if
        zones is set.

    join_fn:
        The function to call on the column and index masks to join them.
        By default, a bitwise and is used. See pythons builtin operator
        library for more options.

    Returns
    -------
    mask:
        A mask of true and false values. Will be the same shape as df.
    """
    # Validate input args
    if zones is None:
        if col_zones is None or index_zones is None:
            raise ValueError(
                "If zones is not set, both col_zones and row_zones need "
                "to be set."
            )
    else:
        col_zones = zones
        index_zones = zones

    # Try and cast to the correct types for rows/cols
    try:
        # Assume columns are strings if they are an object
        col_dtype = df.columns.dtype
        col_dtype = str if col_dtype == object else col_dtype
        col_zones = np.array(col_zones, col_dtype)
    except ValueError:
        raise ValueError(
            "Cannot cast the col_zones to the required dtype to match the "
            "dtype of the given df columns. Tried to cast to: %s"
            % str(df.columns.dtype)
        )

    try:
        index_zones = np.array(index_zones, df.index.dtype)
    except ValueError:
        raise ValueError(
            "Cannot cast the index_zones to the required dtype to match the "
            "dtype of the given df index. Tried to cast to: %s"
            % str(df.index.dtype)
        )

    print(df)
    print(df.shape)

    # Create square masks for the rows and cols
    col_mask = np.broadcast_to(df.columns.isin(col_zones), df.shape)
    index_mask = np.broadcast_to(df.index.isin(index_zones), df.shape).T

    # Combine together to get the full mask
    return join_fn(col_mask, index_mask)


def get_wide_mask_np(a: pd.DataFrame,
                     zones: List[Any] = None,
                     col_zones: List[Any] = None,
                     index_zones: List[Any] = None,
                     join_fn: Callable = operator.and_
                     ) -> np.ndarray:
    """
    Generates a mask for a wide matrix. Returned mask will be same shape as a

    The zones the set the mask for can be set individually with col_zones and
    index_zones, or to the same value with zones.

    Parameters
    ----------
    a:
        The array to generate the mask for

    zones:
        The zones to match to in both the columns and index. If this value
        is set it will overwrite anything passed into col_zones and
        index_zones.

    col_zones:
        The zones to match to in the columns. This value is ignored if
        zones is set.

    index_zones:
        The zones to match to in the index. This value is ignored if
        zones is set.

    join_fn:
        The function to call on the column and index masks to join them.
        By default, a bitwise and is used. See pythons builtin operator
        library for more options.

    Returns
    -------
    mask:
        A mask of true and false values. Will be the same shape as df.
    """
    # Init DF args
    n_rows, n_cols = a.shape
    index = range(n_rows)
    cols = range(n_cols)

    # Call pandas function
    return get_wide_mask(
        df=pd.DataFrame(data=a, index=index, columns=cols),
        zones=zones,
        col_zones=col_zones,
        index_zones=index_zones,
        join_fn=join_fn,
    )


def get_internal_mask(df: Union[pd.DataFrame, np.array],
                      zones: List[Any],
                      ) -> np.ndarray:
    """
    Generates a mask for a wide matrix. Returned mask will be same shape as df

    Parameters
    ----------
    df:
        The dataframe to generate the mask for

    zones:
        A list of zone numbers that make up the internal zones

    Returns
    -------
    mask:
        A mask of true and false values. Will be the same shape as df.
    """
    if isinstance(df, np.ndarray):
        fn = get_wide_mask_np
    else:
        fn = get_wide_mask
    
    return fn(df, zones, operator.and_)


def get_external_mask(df: Union[pd.DataFrame, np.array],
                      zones: List[Any],
                      ) -> np.ndarray:
    """
    Generates a mask for a wide matrix. Returned mask will be same shape as df

    Parameters
    ----------
    df:
        The dataframe to generate the mask for

    zones:
        A list of zone numbers that make up the external zones

    Returns
    -------
    mask:
        A mask of true and false values. Will be the same shape as df.
    """
    if isinstance(df, np.ndarray):
        fn = get_wide_mask_np
    else:
        fn = get_wide_mask

    return fn(df, zones, operator.or_)
