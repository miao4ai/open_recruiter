"""RecruitGPT — a domain-specialised recruiting model, and the pipeline behind it.

See PLAN.md for what this is trying to answer and how the phases are ordered.

The data and evaluation layers deliberately avoid importing torch, so a
contributor can generate a dataset, inspect it, and run the metrics on a laptop.
Training pulls the heavy stack, behind the `train` extra:

    pip install -e ".[train]"
"""

__version__ = "0.1.0"
