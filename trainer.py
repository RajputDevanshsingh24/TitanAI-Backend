# ============================================
# TITAN-AI TRADER — Auto Trainer
# TITAN-SURYA TECHNOLOGIES
# ============================================

from datetime import datetime
from data_fetcher import DataFetcher
from ai_model import AIModel
from config import AI


class AutoTrainer:

    def __init__(self):
        self.fetcher       = DataFetcher()
        self.model         = AIModel()
        self.last_trained  = None
        self.train_count   = 0
        print("✅ AutoTrainer Ready!")

    def train_once(self):
        try:
            print(f"\n{'='*50}")
            print(f"🤖 AUTO TRAINING SHURU!")
            print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")

            if not self.fetcher.connected:
                self.fetcher.connect()

            df = self.fetcher.get_best_data("NIFTY")
            if df is None or len(df) < 100:
                print("❌ Enough data nahi mila training ke liye!")
                return False

            accuracy = self.model.train(df)

            if accuracy >= AI["min_accuracy"]:
                self.last_trained = datetime.now()
                self.train_count += 1
                print(f"\n✅ Training Complete!")
                print(f"   Accuracy:    {accuracy:.2f}%")
                print(f"   Train Count: {self.train_count}")
                return True
            else:
                print(f"\n⚠️ Accuracy too low: {accuracy:.2f}% "
                      f"(min: {AI['min_accuracy']}%)")
                print("   Model save nahi kiya!")
                return False

        except Exception as e:
            print(f"❌ Training Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_status(self):
        return {
            "last_trained" : str(self.last_trained),
            "train_count"  : self.train_count,
            "accuracy"     : self.model.accuracy,
        }