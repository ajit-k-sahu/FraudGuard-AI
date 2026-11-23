"""
Synthetic Financial Transaction Dataset Generator for FraudGuard AI.
Models PaySim mobile money characteristics with real-world fraud typologies.
"""

import os
import random
import numpy as np
import pandas as pd

def generate_transactions(n_samples=15000, fraud_rate=0.035, random_seed=42):
    np.random.seed(random_seed)
    random.seed(random_seed)

    channels = ['Mobile Banking', 'Internet Banking', 'ATM', 'POS', 'UPI']
    locations = ['Domestic', 'High-Risk Domestic', 'Cross-Border (Recognized)', 'Cross-Border (Unusual)']
    devices = ['Mobile App (Recognized)', 'Web Browser (Recognized)', 'New / Unrecognized Device', 'ATM Terminal', 'POS Terminal']
    types = ['Transfer', 'Payment', 'Cash Withdrawal', 'Deposit', 'Purchase']

    n_fraud = int(n_samples * fraud_rate)
    n_legit = n_samples - n_fraud

    records = []

    # 1. Generate Legitimate Transactions
    for i in range(n_legit):
        t_type = random.choices(types, weights=[0.25, 0.35, 0.15, 0.10, 0.15])[0]
        
        # 95% regular retail amounts ($5 to $4,000), 5% legitimate high-value business/wealth transactions ($5,000 to $65,000)
        is_high_value_legit = (random.random() < 0.05)
        if is_high_value_legit:
            amount = float(np.random.uniform(5000.0, 65000.0))
            account_age_days = random.randint(300, 2500)
            frequency_24h = random.randint(1, 3)
            previous_amount = float(np.random.uniform(3000.0, 50000.0))
            device = random.choices(devices, weights=[0.70, 0.28, 0.02, 0.0, 0.0])[0]
            location = random.choices(locations, weights=[0.85, 0.05, 0.10, 0.0])[0]
        else:
            base_amount = float(np.random.lognormal(mean=4.2, sigma=1.1))
            amount = max(5.0, min(4500.0, base_amount))
            frequency_24h = int(np.random.poisson(lam=2.2)) + 1
            account_age_days = int(np.random.exponential(scale=650)) + 30
            prev_ratio = np.random.uniform(0.5, 2.2)
            previous_amount = round(amount * prev_ratio, 2)
            device = random.choices(devices, weights=[0.60, 0.25, 0.05, 0.05, 0.05])[0]
            location = random.choices(locations, weights=[0.82, 0.10, 0.06, 0.02])[0]

        channel = random.choices(channels, weights=[0.40, 0.25, 0.15, 0.10, 0.10])[0]
        
        # Balances
        old_balance_orig = round(amount * np.random.uniform(1.2, 8.0) + np.random.uniform(100, 2000), 2)
        new_balance_orig = round(max(0.0, old_balance_orig - amount), 2) if t_type in ['Transfer', 'Payment', 'Cash Withdrawal', 'Purchase'] else round(old_balance_orig + amount, 2)
        
        old_balance_dest = round(np.random.uniform(50, 5000), 2)
        new_balance_dest = round(old_balance_dest + amount, 2)
        
        records.append({
            'transaction_ref': f'TXN-LEG-{i+100000:06d}',
            'amount': round(amount, 2),
            'transaction_type': t_type,
            'sender_account': f'C{random.randint(1000000, 9999999)}',
            'receiver_account': f'M{random.randint(1000000, 9999999)}' if t_type in ['Payment', 'Purchase'] else f'C{random.randint(1000000, 9999999)}',
            'channel': channel,
            'location': location,
            'device': device,
            'frequency_24h': frequency_24h,
            'account_age_days': account_age_days,
            'previous_amount': round(previous_amount, 2),
            'old_balance_orig': old_balance_orig,
            'new_balance_orig': new_balance_orig,
            'old_balance_dest': old_balance_dest,
            'new_balance_dest': new_balance_dest,
            'is_fraud': 0
        })

    # 2. Generate Fraudulent Transactions (Distinct Typologies including Micro-Fraud)
    fraud_typologies = ['balance_drain', 'velocity_burst', 'new_account_heist', 'ratio_spike', 'cross_border_takeover', 'micro_card_testing']

    for i in range(n_fraud):
        typology = random.choice(fraud_typologies)
        
        if typology == 'micro_card_testing':
            # Low amount probing attack to test compromised credentials
            t_type = random.choice(['Payment', 'Purchase'])
            amount = round(float(np.random.uniform(2.0, 65.0)), 2)
            old_balance_orig = round(float(np.random.uniform(100, 1500)), 2)
            new_balance_orig = round(old_balance_orig - amount, 2)
            old_balance_dest = 10.0
            new_balance_dest = round(old_balance_dest + amount, 2)
            channel = random.choice(['Internet Banking', 'POS'])
            location = random.choice(['High-Risk Domestic', 'Cross-Border (Unusual)'])
            device = 'New / Unrecognized Device'
            frequency_24h = random.randint(12, 35) # High burst of small tests
            account_age_days = random.randint(10, 200)
            previous_amount = round(float(np.random.uniform(10, 80)), 2)

        elif typology == 'balance_drain':
            # Complete balance drain via Transfer or Cash Out
            t_type = random.choice(['Transfer', 'Cash Withdrawal'])
            amount = round(float(np.random.uniform(4000, 85000)), 2)
            old_balance_orig = amount  # Account drained to zero
            new_balance_orig = 0.0
            old_balance_dest = 0.0
            new_balance_dest = amount
            channel = random.choice(['Internet Banking', 'Mobile Banking'])
            location = random.choice(['High-Risk Domestic', 'Cross-Border (Unusual)'])
            device = random.choice(['New / Unrecognized Device', 'Web Browser (Recognized)'])
            frequency_24h = random.randint(4, 18)
            account_age_days = random.randint(40, 500)
            previous_amount = round(float(np.random.uniform(50, 400)), 2)
            
        elif typology == 'velocity_burst':
            # Rapid high-frequency attacks
            t_type = random.choice(['Transfer', 'Payment', 'Cash Withdrawal'])
            amount = round(float(np.random.uniform(800, 12000)), 2)
            old_balance_orig = round(amount * 1.3, 2)
            new_balance_orig = round(old_balance_orig - amount, 2)
            old_balance_dest = 0.0
            new_balance_dest = amount
            channel = random.choice(['Mobile Banking', 'UPI', 'Internet Banking'])
            location = random.choice(['Domestic', 'High-Risk Domestic'])
            device = 'New / Unrecognized Device'
            frequency_24h = random.randint(16, 55)  # Very abnormal velocity
            account_age_days = random.randint(20, 300)
            previous_amount = round(float(np.random.uniform(40, 250)), 2)

        elif typology == 'new_account_heist':
            # Brand new account with immediate massive outbound transfer
            t_type = 'Transfer'
            amount = round(float(np.random.uniform(6000, 65000)), 2)
            old_balance_orig = amount
            new_balance_orig = 0.0
            old_balance_dest = 100.0
            new_balance_dest = round(old_balance_dest + amount, 2)
            channel = random.choice(['Internet Banking', 'Mobile Banking'])
            location = 'Cross-Border (Unusual)'
            device = 'New / Unrecognized Device'
            frequency_24h = random.randint(1, 4)
            account_age_days = random.randint(1, 14)  # Under 2 weeks old
            previous_amount = round(float(np.random.uniform(0, 100)), 2)

        elif typology == 'ratio_spike':
            # Huge spike compared to normal historical spending
            t_type = random.choice(['Transfer', 'Purchase'])
            amount = round(float(np.random.uniform(4500, 35000)), 2)
            old_balance_orig = round(amount + 400.0, 2)
            new_balance_orig = 400.0
            old_balance_dest = 250.0
            new_balance_dest = round(old_balance_dest + amount, 2)
            channel = random.choice(['Internet Banking', 'POS'])
            location = random.choice(['High-Risk Domestic', 'Cross-Border (Unusual)'])
            device = 'New / Unrecognized Device'
            frequency_24h = random.randint(5, 15)
            account_age_days = random.randint(60, 600)
            previous_amount = round(float(np.random.uniform(20, 120)), 2)

        else: # cross_border_takeover
            t_type = 'Transfer'
            amount = round(float(np.random.uniform(8000, 95000)), 2)
            old_balance_orig = round(amount * 1.05, 2)
            new_balance_orig = round(old_balance_orig - amount, 2)
            old_balance_dest = 0.0
            new_balance_dest = amount
            channel = 'Internet Banking'
            location = 'Cross-Border (Unusual)'
            device = 'New / Unrecognized Device'
            frequency_24h = random.randint(7, 22)
            account_age_days = random.randint(90, 800)
            previous_amount = round(float(np.random.uniform(100, 500)), 2)

        records.append({
            'transaction_ref': f'TXN-FRD-{i+100000:06d}',
            'amount': amount,
            'transaction_type': t_type,
            'sender_account': f'C{random.randint(1000000, 9999999)}',
            'receiver_account': f'C{random.randint(1000000, 9999999)}',
            'channel': channel,
            'location': location,
            'device': device,
            'frequency_24h': frequency_24h,
            'account_age_days': account_age_days,
            'previous_amount': previous_amount,
            'old_balance_orig': old_balance_orig,
            'new_balance_orig': new_balance_orig,
            'old_balance_dest': old_balance_dest,
            'new_balance_dest': new_balance_dest,
            'is_fraud': 1
        })

    df = pd.DataFrame(records)
    # Shuffle dataset
    df = df.sample(frac=1.0, random_state=random_seed).reset_index(drop=True)
    return df

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, 'dataset', 'synthetic_transactions.csv')
    
    print("Generating synthetic financial transactions dataset...")
    df = generate_transactions(n_samples=15000, fraud_rate=0.035, random_seed=42)
    df.to_csv(output_path, index=False)
    
    print(f"Dataset successfully generated at: {output_path}")
    print(f"Total records: {len(df)}")
    print(f"Legitimate count: {len(df[df['is_fraud'] == 0])}")
    print(f"Fraud count: {len(df[df['is_fraud'] == 1])}")
    print(f"Fraud rate: {df['is_fraud'].mean():.2%}")
