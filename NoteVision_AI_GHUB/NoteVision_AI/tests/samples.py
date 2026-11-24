import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLE = """Machine learning is a branch of artificial intelligence that lets computers learn from data.
Supervised learning is a type of machine learning where the model is trained on labeled data. Classification and regression are two common supervised learning tasks.
Unsupervised learning finds hidden patterns in unlabeled data, whereas supervised learning needs labels. Clustering is an example of unsupervised learning.
Overfitting occurs when a model memorizes the training data and performs poorly on new data. Cross-validation is a technique used to detect overfitting in a model.
A decision tree is a model that splits data into branches using feature values. Neural networks are models inspired by the human brain.
Gradient descent is an optimization algorithm that minimizes the loss function. The learning rate controls the size of each step in gradient descent.
Accuracy measures the proportion of correct predictions. Precision measures how many predicted positives are truly positive."""
