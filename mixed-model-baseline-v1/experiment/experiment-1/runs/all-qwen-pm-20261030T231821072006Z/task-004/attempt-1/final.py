from typing import List

def mean_absolute_deviation(numbers: List[float]) -> float:
    """
    For a given list of input numbers, calculate Mean Absolute Deviation
    around the mean of this dataset.
    Mean Absolute Deviation is the average absolute difference between each
    element and the mean of the dataset:
    MAD = average | x - x_mean |
    >>> mean_absolute_deviation([1.0, 2.0, 3.0, 4.0])
    1.0
    """
    if not numbers:
        return 0.0

    # Calculate the mean
    mean = sum(numbers) / len(numbers)

    # Calculate the total absolute difference from the mean
    total_diff = sum(abs(x - mean) for x in numbers)

    # Compute the mean absolute deviation
    mad = total_diff / len(numbers)

    return mad
