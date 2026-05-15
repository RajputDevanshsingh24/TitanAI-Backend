# ============================================
# TITAN-AI TRADER — Auto Trainer
# TITAN-SURYA TECHNOLOGIES
# ============================================

import schedule
import time
import os
import json
import pickle
from datetime import datetime
from data_fetcher import DataFetcher
from ai_model import AIModel

class AutoTrainer:

    def __init__(self):
        self.fetcher      = DataFetcher()
        self.model        = AIModel()
        self.log_path     = "training_logs/"
        self.best_acc     = 0
        os.makedirs(self.log_path, exist_ok=True)
        self._load_best_accuracy()

    # ============================================
    # BEST ACCURACY LOAD KARO
    # ============================================
    def _load_best_accuracy(self):
        try:
            acc_file = "models/accuracy.txt"
            if os.path.exists(acc_file):
                with open(acc_file, "r") as f:
                    self.best_acc = float(f.read())
                print(f"📊 Current Best Accuracy: {self.best_acc:.2f}%")
        except:
            self.best_acc = 0

    # ============================================
    # LOG SAVE KARO
    # ============================================
    def _save_log(self, data):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"{self.log_path}train_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"📝 Log saved: {filename}")
        except Exception as e:
            print(f"❌ Log Error: {e}")

    # ============================================
    # EK TRAINING CYCLE
    # ============================================
    def train_once(self):
        print("\n" + "="*50)
        print(f"🔄 TRAINING CYCLE SHURU")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)

        try:
            # Step 1: Connect karo
            if not self.fetcher.connected:
                self.fetcher.connect()

            # Step 2: Fresh data lo
            print("\n📊 Naya data fetch ho raha hai...")
            df = self.fetcher.get_historical_data(
                "NIFTY", days=365
            )
            if df is None:
                print("❌ Data nahi mila! Training skip.")
                return False

            # Step 3: Naya model train karo
            print("\n🤖 Naya model train ho raha hai...")
            new_model    = AIModel()
            new_accuracy = new_model.train(df)

            # Step 4: Purane model se compare karo
            print(f"\n📊 COMPARISON:")
            print(f"   Purana Model: {self.best_acc:.2f}%")
            print(f"   Naya Model:   {new_accuracy:.2f}%")

            # Step 5: Better hai toh deploy karo
            if new_accuracy > self.best_acc:
                improvement    = new_accuracy - self.best_acc
                self.best_acc  = new_accuracy
                self.model     = new_model
                status         = "IMPROVED"
                print(f"\n✅ NAYA MODEL BETTER HAI!")
                print(f"   Improvement: +{improvement:.2f}%")
                print(f"   Deploying new model...")
            else:
                diff   = self.best_acc - new_accuracy
                status = "KEPT OLD"
                print(f"\n⚠️ Purana model better hai")
                print(f"   Difference: -{diff:.2f}%")
                print(f"   Purana model rakha gaya")

            # Step 6: Log save karo
            log = {
                "timestamp"    : datetime.now().strftime(
                                  "%Y-%m-%d %H:%M:%S"),
                "new_accuracy" : new_accuracy,
                "best_accuracy": self.best_acc,
                "status"       : status,
                "data_rows"    : len(df),
            }
            self._save_log(log)

            print(f"\n✅ Training cycle complete!")
            return True

        except Exception as e:
            print(f"❌ Training Error: {e}")
            return False

    # ============================================
    # TRAINING HISTORY DEKHO
    # ============================================
    def get_history(self):
        try:
            logs   = []
            files  = sorted(os.listdir(self.log_path))
            
            for f in files[-10:]:  # Last 10 trainings
                path = os.path.join(self.log_path, f)
                with open(path, "r") as file:
                    logs.append(json.load(file))

            print("\n📋 TRAINING HISTORY (Last 10):")
            print("-"*55)
            print(f"{'Date':<22} {'Accuracy':>10} {'Status':<15}")
            print("-"*55)
            
            for log in logs:
                print(
                    f"{log['timestamp']:<22} "
                    f"{log['new_accuracy']:>9.2f}% "
                    f"{log['status']:<15}"
                )
            print("-"*55)
            print(f"Best Accuracy: {self.best_acc:.2f}%")
            
            return logs

        except Exception as e:
            print(f"❌ History Error: {e}")
            return []

    # ============================================
    # AUTO SCHEDULE — Raat 11 PM
    # ============================================
    def start_auto_training(self):
        print("\n" + "="*50)
        print("⏰ AUTO TRAINING SCHEDULER SHURU!")
        print(f"   Schedule: Raat 11:00 PM daily")
        print(f"   Abhi time: {datetime.now().strftime('%H:%M:%S')}")
        print("="*50)

        # Har raat 11 baje train karo
        schedule.every().day.at("23:00").do(self.train_once)

        # Market band hone ke baad bhi train karo
        schedule.every().day.at("16:00").do(self.train_once)

        print("\n✅ Scheduler ready!")
        print("   Bot automatically train hoga:")
        print("   → Roz 4:00 PM (Market band ke baad)")
        print("   → Roz 11:00 PM (Raat mein)")
        print("\n   Ctrl+C dabao band karne ke liye\n")

        while True:
            schedule.run_pending()
            
            # Har 1 minute mein time show karo
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\r⏰ Running... {now} | "
                  f"Best Accuracy: {self.best_acc:.2f}%",
                  end="", flush=True)
            time.sleep(60)


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    trainer = AutoTrainer()

    print("\nKya karna hai?")
    print("1. Abhi ek baar train karo")
    print("2. Auto training shuru karo (24/7)")
    print("3. Training history dekho")

    choice = input("\nChoice (1/2/3): ").strip()

    if choice == "1":
        trainer.train_once()

    elif choice == "2":
        trainer.start_auto_training()

    elif choice == "3":
        trainer.get_history()

    else:
        print("❌ Invalid choice!")