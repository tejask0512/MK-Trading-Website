import os
import pandas as pd
import numpy as np
from datetime import datetime
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from datasets import load_dataset
import torch
import config

from dotenv import load_dotenv
import os
# Configuration
DATA_DIR = config.DATA_DIR

import os
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
df = pd.read_csv(os.path.join(data_dir, "News_live.csv"))


MODEL_PATH = os.environ.get('MODEL_PATH', None)  # Set if using a custom model
USE_CUSTOM_MODEL = os.environ.get('USE_CUSTOM_MODEL', 'false').lower() == 'true'

HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
# Ensure directories exist
#os.makedirs(DATA_DIR, exist_ok=True)
#os.makedirs(CHARTS_DIR, exist_ok=True)

def load_sentiment_model():
    """Load either a pre-trained model or a custom fine-tuned model"""
    print("Loading sentiment analysis model...")
    
    if USE_CUSTOM_MODEL and MODEL_PATH:
        # Load custom fine-tuned model
        print(f"Using custom model from {MODEL_PATH}")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
        classifier = pipeline("text-classification", model=model, tokenizer=tokenizer)
    else:
        # Use pre-trained financial sentiment model
        print("Using pre-trained financial sentiment model")
        classifier = pipeline(
            "text-classification", 
            model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis", 
            token=HUGGING_FACE_TOKEN
        )
    
    return classifier

def analyze_news_batch(texts, classifier, batch_size=8):
    """Process news texts in batches to prevent memory issues"""
    results = []
    
    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_results = classifier(batch)
        results.extend(batch_results)
    
    return results

def analyze_sentiment(input_file=None):
    """
    Analyze sentiment of news articles and save results to CSV
    
    Args:
        input_file: Path to the input CSV file with news data
                   If None, uses the default path
    
    Returns:
        DataFrame with sentiment analysis results
    """
    if input_file is None:
        input_file = os.path.join(DATA_DIR, 'News_live.csv')
        news_df = pd.read_csv(input_file)
        
    output_file = df.to_csv(os.path.join(data_dir, "sentiment_results.csv"), index=False)
    
    print(f"Starting sentiment analysis on {input_file}...")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return None
    
    # Load the news data
    news_df = pd.read_csv(input_file)
    news_df.fillna({'description':"No description available"}, inplace=True)
    print(news_df)
    # Clean up column names if needed
   
    # Load the sentiment analysis model
    classifier = load_sentiment_model()
    
    # Combine title and description for better context
    news_df['FullText'] = news_df['title'].astype(str) + ". " + news_df['description'].astype(str)
    
    # Process all texts in optimized batches
    print("Analyzing sentiment for news items...")
    all_texts = news_df['FullText'].tolist()
    batch_results = analyze_news_batch(all_texts, classifier)
    
    # Create results with detailed sentiment information
    results = []
    
    for index, (row, sentiment_result) in enumerate(zip(news_df.iterrows(), batch_results)):
        row = row[1]  # Get the actual row data
        sentiment_label = sentiment_result['label']
        confidence = sentiment_result['score']
        
        # Calculate individual scores based on the model output
        positive_score = confidence if sentiment_label == 'positive' else 0
        neutral_score = confidence if sentiment_label == 'neutral' else 0
        negative_score = confidence if sentiment_label == 'negative' else 0
        
        # Impact calculation
        impact_score = positive_score - negative_score
        
        # Store results
        results.append({
            'title': row['title'],
            'description': row['description'],
            'date': row['date'],
            'source': row['source'],
            'url': row.get('url', ''),
            'sentiment': sentiment_label,
            'confidence': confidence,
            'positive_Score': positive_score,
            'neutral_Score': neutral_score,
            'negative_Score': negative_score,
            'impact_Score': impact_score
        })
    
    # Create a DataFrame with results
    sentiment_df = pd.DataFrame(results)
    
    # Save results to CSV
    sentiment_df.to_csv(output_file, index=False)
    print(f"Sentiment analysis complete. Results saved to {output_file}")
    
    return sentiment_df

def fine_tune_custom_model(save_path=None):
    """
    Fine-tune a custom sentiment model using Indian financial news
    
    Args:
        save_path: Path to save the fine-tuned model
                  If None, uses a default path
    
    Returns:
        Path to the saved model
    """
    if save_path is None:
        save_path = os.path.join(DATA_DIR, 'custom_sentiment_model')
    
    print("Loading Indian Financial News dataset...")
    try:
        news_dataset = load_dataset("kdave/Indian_Financial_News")
        
        # Process and prepare the dataset
        # This is simplified - you'd need to adapt this to the actual dataset structure
        train_data = news_dataset['train']
        
        print(f"Loaded {len(train_data)} training examples")
        
        # Load a base model to fine-tune
        model_name = "distilbert-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, 
            num_labels=3  # positive, neutral, negative
        )
        
        # Fine-tuning process would go here
        # This is just a placeholder - actual implementation would use 
        # the Trainer API from transformers or similar
        
        print(f"Saving fine-tuned model to {save_path}")
        model.save_pretrained(save_path)
        tokenizer.save_pretrained(save_path)
        
        return save_path
    
    except Exception as e:
        print(f"Error fine-tuning custom model: {e}")
        return None

if __name__ == "__main__":
    # Command line argument handling could be added here
    sentiment_df = analyze_sentiment()
   