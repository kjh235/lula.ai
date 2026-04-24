import numpy as np
from collections import defaultdict
from app.sizing import FAMILY_LADDERS, size_to_ordinal, ordinal_to_size, normalize_size


class SizeFitModel:
    """Latent-factor size fit model per sizing family.

    Each customer c has a latent true size s_c (real-valued ordinal position).
    Each product p has a latent size offset t_p (how much it runs large/small).

    For a given (customer, product, size), the fit probability is modeled as:
        P(true_to_size) ~ exp(-0.5 * ((s_c - (ordinal(size) + t_p)) / sigma)^2)

    Fit outcomes shift s_c:
        too_small  -> customer is larger than the size they bought
        too_large  -> customer is smaller than the size they bought
        true_to_size -> size matches
    """

    def __init__(self):
        self.customer_size = {}
        self.product_offset = {}
        self.sigma = 0.8
        self.family = None

    def fit(self, feedback_records, family, lr=0.05, epochs=50):
        """Train the model on fit feedback data.

        Args:
            feedback_records: list of dicts with keys:
                'customer_id', 'product_sku', 'size_purchased', 'fit_outcome'
            family: sizing family string
            lr: learning rate
            epochs: training iterations
        """
        self.family = family
        ladder = FAMILY_LADDERS.get(family, {})
        if not ladder or not feedback_records:
            return

        customer_ids = list({r['customer_id'] for r in feedback_records})
        product_skus = list({r['product_sku'] for r in feedback_records})

        s_c = {}
        t_p = {}
        mid = len(ladder) / 2.0
        for cid in customer_ids:
            sizes_bought = [
                size_to_ordinal(r['size_purchased'], family)
                for r in feedback_records
                if r['customer_id'] == cid and size_to_ordinal(r['size_purchased'], family) is not None
            ]
            s_c[cid] = np.mean(sizes_bought) if sizes_bought else mid
        for sku in product_skus:
            t_p[sku] = 0.0

        outcome_target = {
            'too_small': 1.0,
            'true_to_size': 0.0,
            'too_large': -1.0,
        }

        for epoch in range(epochs):
            np.random.shuffle(feedback_records)
            total_loss = 0.0
            for rec in feedback_records:
                cid = rec['customer_id']
                sku = rec['product_sku']
                size_ord = size_to_ordinal(rec['size_purchased'], family)
                if size_ord is None:
                    continue
                target = outcome_target.get(rec['fit_outcome'], 0.0)
                residual = s_c[cid] - (size_ord + t_p[sku])
                error = residual - target
                total_loss += error ** 2

                s_c[cid] -= lr * error
                t_p[sku] += lr * error

        self.customer_size = dict(s_c)
        self.product_offset = dict(t_p)

    def predict_best_size(self, customer_id, product_sku, family=None):
        """Predict the best size for a customer-product pair.

        Returns:
            (best_size_token, confidence) or (None, 'low') if no data
        """
        fam = family or self.family
        if not fam:
            return None, 'low'

        ladder = FAMILY_LADDERS.get(fam, {})
        if not ladder:
            return None, 'low'

        s_c = self.customer_size.get(customer_id)
        t_p = self.product_offset.get(product_sku, 0.0)

        if s_c is None:
            return None, 'low'

        ideal_ordinal = s_c - t_p

        unique_ordinals = sorted(set(ladder.values()))
        best_ord = min(unique_ordinals, key=lambda o: abs(o - ideal_ordinal))
        best_size = ordinal_to_size(best_ord, fam)

        dist = abs(best_ord - ideal_ordinal)
        if dist < 0.3:
            confidence = 'high'
        elif dist < 0.7:
            confidence = 'medium'
        else:
            confidence = 'low'

        return best_size, confidence

    def predict_size_fallback(self, customer_purchase_sizes, family):
        """Fallback when customer/product not in training data.
        Returns the mode of their purchased sizes in this family."""
        if not customer_purchase_sizes:
            return None
        counter = defaultdict(int)
        for s in customer_purchase_sizes:
            norm = normalize_size(s)
            counter[norm] += 1
        return max(counter, key=counter.get)
