def _normalize_array(data: np.ndarray) -> np.ndarray:
    """Normalizes numpy array to unit scale.
    
    Args:
        data: Input array of any shape
    
    Returns:
        np.ndarray: Normalized array with values in [0,1]
    
    Raises:
        ValueError: If input contains NaN/inf values
    """
    return (data - np.min(data)) / (np.max(data) - np.min(data))