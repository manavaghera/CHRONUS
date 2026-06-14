import pandas as pd

# ---- LOAD ----
df = pd.read_csv('elon_musk_cleaned.csv')
print(f"Starting tweets: {len(df)}")

# 1. Remove retweets
df = df[df['is_rt'] == False]
print(f"After removing RTs: {len(df)}")

# 2. Remove link-only tweets (just a URL, nothing else)
df = df[~df['text'].str.match(r'^https?://\S+$', na=False)]
print(f"After removing link-only: {len(df)}")

# 3. Remove tweets under 5 words
df = df[df['text'].str.split().str.len() >= 5]
print(f"After removing <5 words: {len(df)}")

# 4. Remove duplicates
df = df.drop_duplicates(subset=['text'])
print(f"After removing duplicates: {len(df)}")

# 5. Keep only Elon's original tweets
df = df[df['is_elon_original'] == True]
print(f"After keeping only originals: {len(df)}")

# ---- SAVE ----
df.to_csv('elon-tweets-cleaned.csv', index=False)
print(f"\nFinal cleaned tweets: {len(df)}")
print("Saved to elon-tweets-cleaned.csv")
