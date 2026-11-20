import { useCallback, useEffect, useRef, useState } from 'react';
import { uuid } from 'expo';
import { Keyboard, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useTodaySteps } from '../../services/health/useTodaySteps';
import { getBalance } from '../../services/api/balance';
import { getAssets } from '../../services/api/market';
import { buyShares as placeBuyOrder } from '../../services/api/trading';
import { getPortfolio } from '../../services/api/portfolio';

// Turns cents into dollars for display. 100000 -> "1,000.00"
// show the 2 decimal places even if they are 0, and use commas for thousands
function formatMoney(cents: number) {
  return (cents / 100).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Most credits steps can earn in one day, shown in the daily limit bar.
const DAILY_CREDIT_LIMIT = 300;

// Usual earning rate, shown until the server sends its own rate.
const DEFAULT_STEPS_PER_CREDIT = 100;

// Turns a server amount like "1062.0000" into cents (106200).
function toCents(text: string) {
  const [whole, fraction = ''] = text.split('.');
  return Number(whole) * 100 + Number((fraction + '00').slice(0, 2));
}

// Reward fields used by this screen; the shared response type is still generic.
type StepSyncResult = {
  cash_balance: string;
  steps_per_coin: number;
  totals: {
    step_count: number;
    reward: string;
    counted: boolean;
  }[];
};

export default function DemoScreen() {
   // Today's steps from the phone (null if not read yet or unavailable), and whether it is still loading.
  const { steps, loading, syncError, syncResult: result } = useTodaySteps();

  // Describe the reward fields returned by the server.
  const syncResult = result as StepSyncResult | null;
  // Today's result is unavailable until the first sync succeeds.
  const todayResult = syncResult?.totals?.[0];

  // Keep the bar empty until the server returns today's earnings.
  const todayReward = todayResult ? Number(todayResult.reward) : 0;

  // Balance in cents, null until the server sends it
  const [balance, setBalance] = useState<number | null>(null);

  // True if the balance could not be loaded from the server
  const [balanceFailed, setBalanceFailed] = useState(false);

  // Get the balance from the server once, when the screen opens
  useEffect(() => {
    getBalance()
      .then(data => setBalance(toCents(data.cash_balance)))
      .catch(() => setBalanceFailed(true));
  }, []);

  // AAPL price from the server, e.g. "120.2300", null until it arrives
  const [priceText, setPriceText] = useState<string | null>(null);

  // True if the price could not be loaded from the server
  const [priceFailed, setPriceFailed] = useState(false);

  // Gets the AAPL price from the server
  const loadPrice = useCallback(() => {
    getAssets()
      .then(data => {
        const aapl = data.assets.find(asset => asset.symbol === 'AAPL');
        setPriceText(aapl?.price ?? null);
        setPriceFailed(false);
      })
      .catch(() => setPriceFailed(true));
  }, []);

  // Get the AAPL price now, then again every 60 seconds
  useEffect(() => {
    loadPrice();
    const timer = setInterval(loadPrice, 60000);
    return () => clearInterval(timer);
  }, [loadPrice]);

  // Price in cents, null until it arrives
  const sharePrice = priceText !== null ? toCents(priceText) : null;

  // Show the server's balance after each successful step sync.
  useEffect(() => {
    if (syncResult) {
      setBalance(toCents(syncResult.cash_balance));
    }
  }, [syncResult]);

  // AAPL shares and their value from the server, null until they arrive
  const [sharesHeld, setSharesHeld] = useState<number | null>(null);
  const [holdingsValue, setHoldingsValue] = useState<number | null>(null);
  // True if the portfolio could not be loaded from the server
  const [portfolioFailed, setPortfolioFailed] = useState(false);
  const portfolioRequest = useRef(0);

  // Gets the AAPL shares and the holdings value from the server
  const loadPortfolio = useCallback(async () => {
    const request = ++portfolioRequest.current;
    try {
      const data = await getPortfolio();
      if (request !== portfolioRequest.current) return;
      const aapl = data.holdings.find(holding => holding.symbol === 'AAPL');
      setSharesHeld(aapl?.quantity ?? 0);
      setHoldingsValue(toCents(data.holdings_value));
      setPortfolioFailed(false);
    } catch {
      if (request === portfolioRequest.current) setPortfolioFailed(true);
    }
  }, []);

  // Load the portfolio now, then again every 60 seconds
  useEffect(() => {
    void loadPortfolio();
    const timer = setInterval(loadPortfolio, 60000);
    return () => {
      clearInterval(timer);
      portfolioRequest.current++;
    };
  }, [loadPortfolio]);

  const portfolioStatus = portfolioFailed ? 'Unavailable' : 'Loading…';

  // Store the quantity entered in the input
  const [quantity, setQuantity] = useState('');

  // Store a message when a purchase cannot proceed
  const [error, setError] = useState('');

  const [success, setSuccess] = useState('');

  // Hide the purchase confirmation after three seconds.
  useEffect(() => {
    if (success === '') return;
    const timer = setTimeout(() => setSuccess(''), 3000);
    return () => clearTimeout(timer);
  }, [success]);

  const [buying, setBuying] = useState(false);
  const buyInFlight = useRef(false);
  // Reuse the ID when the user retries the same order after a lost reply.
  const buyRequestId = useRef<string | null>(null);

  // Check that the quantity contains digits and is a positive whole number
  const shareCount = Number(quantity);

  // The quantity is valid only if it is:
  //digits only (no letters, decimals, spaces or minus sign)
  //small enough for JavaScript to store exactly
  //at least 1
  const validQuantity =
    /^\d+$/.test(quantity) &&
    Number.isSafeInteger(shareCount) &&
    shareCount > 0;

  // Calculate the total in cents when the quantity is valid
  const orderTotal = validQuantity && sharePrice !== null ? shareCount * sharePrice : 0;

  // Validate the order before sending it to the trading API.
  async function buyShares() {
    if (buyInFlight.current) return;
    setSuccess('');
    // Stop if the quantity is empty, not a whole number, or 0
    if (!validQuantity) {
      setError('Enter a positive whole number of shares.');
      return;
    }
    // Stop if the total is too big to calculate exactly
    if (!Number.isSafeInteger(orderTotal)) {
      setError('The quantity is too large.');
      return;
    }
    // Stop if the price has not loaded yet
    if (sharePrice === null || priceText === null) {
      setError('Price is not loaded yet.');
      return;
    }

    // Stop if the balance has not loaded yet
    if (balance === null) {
      setError('Balance is not loaded yet.');
      return;
    }
    // Stop if the order costs more than the current balance
    if (orderTotal > balance) {
      setError('Not enough balance for this purchase.');
      return;
    }

    buyInFlight.current = true;
    setBuying(true);
    setError('');
    try {
      buyRequestId.current ??= uuid.v4();
      const receipt = await placeBuyOrder({
        request_id: buyRequestId.current,
        symbol: 'AAPL',
        trade_type: 'buy',
        quantity: shareCount,
        expected_price: priceText,
      });
      setBalance(toCents(receipt.cash_balance));
      void loadPortfolio();
      buyRequestId.current = null;
      setQuantity('');
      setSuccess('Successful purchase');
      Keyboard.dismiss();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Purchase failed. Try again.');
      // The price may have changed, so show the latest one before the user tries again.
      loadPrice();
    } finally {
      buyInFlight.current = false;
      setBuying(false);
    }
  }

  // Clear the previous error when the quantity changes
  function changeQuantity(value: string) {
    if (buyInFlight.current) return;
    if (value !== quantity) buyRequestId.current = null;
    setQuantity(value);
    setError('');
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>FitFolio</Text>

      <View style={styles.summary}>
        {/* Steps box: today's steps from the phone, "Loading…" or "Unavailable" */}
        <View style={styles.card}>
          <Text style={styles.label}>Today's steps</Text>
          <Text style={[styles.number, (loading || steps === null) && styles.label]} numberOfLines={1} adjustsFontSizeToFit>
            {loading ? 'Loading…' : steps === null ? 'Unavailable' : steps.toLocaleString('en-US')}
          </Text>
          <Text style={styles.caption}>steps today</Text>
        </View>

        {/* Balance from the server, updated after step sync and after a purchase */}
        <View style={styles.card}>
          <Text style={styles.label}>Balance</Text>
          <Text style={[styles.number, balance === null && styles.label]} numberOfLines={1} adjustsFontSizeToFit> 
          {balance !== null ? `$${formatMoney(balance)}` : balanceFailed ? 'Unavailable' : 'Loading…'}
          </Text>
          <Text style={styles.caption}>virtual credits</Text>
        </View>
      </View>

      {/* Earned box: how today's steps turned into credits, from the server's reply */}
      <View style={styles.earnedCard}>
        <View style={styles.row}>
          <Text style={styles.sectionTitle}>Earned from steps today</Text>
          {/* Use the server's earning rate, or the default while waiting. */}
          <Text style={styles.ratePill}>
            {syncResult ? syncResult.steps_per_coin : DEFAULT_STEPS_PER_CREDIT} steps = 1 credit
          </Text>
        </View>

        {/* Credits earned today (0 until steps are synced) */}
        <Text style={styles.earned}>+{todayReward} credits</Text>

        {/* Only shown when today's steps were too many to count */}
        {todayResult && !todayResult.counted && (
          <Text style={styles.math}>Not counted: too many steps for one day.</Text>
        )}

        {/* Shown only if sending steps to the server failed */}
        {syncError && <Text style={styles.caption}>{syncError.message}</Text>}

        {/* Always show the bar, show earned progress only after a successful sync. */}
        <View style={styles.limitBar}>
          <View style={[styles.limitFill, { width: `${Math.min(100, (todayReward / DAILY_CREDIT_LIMIT) * 100)}%` }]} />
        </View>
        <Text style={styles.caption}>Daily limit: {DAILY_CREDIT_LIMIT} credits</Text>
      </View>

      {/* Stock price and purchase controls */}
      <View style={styles.stockCard}>
        {/* Green header: company, symbol and price from the server */}
        <View style={styles.stockHeader}>
          <View style={styles.row}>
            <Text style={styles.companyName}>Apple Inc.</Text>
            <Text style={styles.usdBadge}>USD</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.symbol}>AAPL</Text>
            <Text style={[styles.price, sharePrice === null && styles.priceMissing]}>
              {sharePrice !== null ? `$${formatMoney(sharePrice)}` : priceFailed ? 'Unavailable' : 'Loading…'}
            </Text>
          </View>
          <Text style={styles.priceNote}>price per share</Text>
        </View>

        {/* White part: quantity, Buy button and order total */}
        <View style={styles.stockBody}>
          <Text style={styles.quantityLabel}>Quantity</Text>

          <View style={styles.orderRow}>
            <TextInput
              style={styles.input}
              value={quantity}
              editable={!buying}
              onChangeText={changeQuantity}
              keyboardType="number-pad"
              placeholder="Enter shares"
              placeholderTextColor="#69737E"
              accessibilityLabel="Number of shares to buy" />

            {/* Send the purchase to the server when Buy is pressed */}
            <TouchableOpacity
              style={[styles.buyButton, buying && styles.buyButtonBusy]}
              disabled={buying}
              onPress={buyShares}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="Buy AAPL shares">
              <Text style={styles.buyButtonText}>{buying ? 'Buying…' : 'Buy'}</Text>
            </TouchableOpacity>
          </View>

          {/* Total cost for the entered quantity */}
          <View style={styles.orderTotal}>
            <Text style={styles.label}>Order total</Text>
            {/* display the total cost of the order in dollars as $0.00 */}
            <Text style={styles.totalText}>
              ${formatMoney(orderTotal)}
            </Text>
          </View>

          {/* Show a message only when a purchase fails */}
          {error !== '' && (
            <Text style={styles.error} accessibilityRole="alert">
              {error}
            </Text>
          )}

          {success !== '' && (
            <Text style={styles.success} accessibilityRole="alert">
              {success}
            </Text>
          )}
        </View>
      </View>

      {/* Portfolio from the server, refreshed after a purchase and every 60 seconds */}
      <View style={styles.portfolioCard}>
        <View style={styles.row}>
          <Text style={styles.sectionTitle}>Your portfolio</Text>

          {/* Reminds the user these are not real holdings */}
          <Text style={styles.currency}>Simulated</Text>
        </View>

        <View style={styles.holdingRow}>
          <Text style={styles.label}>AAPL shares held</Text>
          <Text style={[styles.shareCount, sharesHeld === null && styles.label]}>
            {sharesHeld ?? portfolioStatus}
          </Text>
        </View>

        <View style={styles.valueRow}>
          <Text style={styles.label}>Holdings value</Text>
          <Text style={[styles.holdingsValue, holdingsValue === null && styles.label]}>
            {holdingsValue === null ? portfolioStatus : `$${formatMoney(holdingsValue)}`}
          </Text>
        </View>

        <Text style={styles.portfolioNote}>
          Your share value. Balance not included.
        </Text>
      </View>

      <Text style={styles.footer}>No real money is used.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
    // ----- Screen -----

  // Whole screen: fills the phone, light grey background
  screen: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  // Space around and between all the boxes on the screen
  content: {
    paddingHorizontal: 20,
    paddingTop: 80,
    paddingBottom: 40,
    gap: 16,
  },
  // "FitFolio" title at the top
  title: {
    fontSize: 28,
    fontWeight: '600',
    color: '#171D22',
  },

  // ----- Steps and balance boxes -----

  // Row that holds the steps box and the balance box side by side
  summary: {
    flexDirection: 'row',
    gap: 12,
  },
  
  // White box used for the steps box and the balance box
  card: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 10,
  },
  // Small grey heading, e.g. "Today's steps", "Balance", "Quantity"
  label: {
    fontSize: 14,
    color: '#69737E',
  },
  // Large number in the steps and balance boxes, e.g. "6,840"
  number: {
    fontSize: 30,
    fontWeight: '600',
    color: '#171D22',
    marginTop: 8,
    marginBottom: 4,
  },
  // Smallest grey text, e.g. "steps today", "Order total"
  caption: {
    fontSize: 12,
    color: '#69737E',
  },

  // ----- Stock box -----

  // White box that holds the stock, quantity and Buy button
  stockCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    overflow: 'hidden',
  },
  // Light green top part with the name and price
  stockHeader: {
    backgroundColor: '#E1F5EE',
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  // White bottom part with quantity, Buy and order total
  stockBody: {
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  // Company name, "Apple Inc."
  companyName: {
    fontSize: 14,
    color: '#0F6E56',
  },
  // Green "USD" badge in the header
  usdBadge: {
    fontSize: 11,
    color: '#085041',
    borderWidth: 1,
    borderColor: '#5DCAA5',
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 4,
  },
  // Stock symbol, "AAPL"
  symbol: {
    fontSize: 24,
    fontWeight: '700',
    color: '#085041',
    marginTop: 8,
  },
  // Share price, e.g. "$120.23"
  price: {
    fontSize: 30,
    fontWeight: '700',
    color: '#085041',
    marginTop: 8,
  },
  // Smaller price text while loading or unavailable
  priceMissing: {
    fontSize: 16,
    fontWeight: '500',
  },
  // "price per share" under the price
  priceNote: {
    fontSize: 13,
    color: '#0F6E56',
    textAlign: 'right',
  },
  // "Quantity" above the input
  quantityLabel: {
    fontSize: 15,
    color: '#3D454D',
  },
  // Row that holds the quantity box and the Buy button side by side
  orderRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
  // Quantity box where the user types the number of shares
  input: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderColor: '#D9DEE3',
    borderRadius: 11,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#171D22',
  },
  // Green Buy button
  buyButton: {
    backgroundColor: '#087B51',
    borderRadius: 11,
    paddingHorizontal: 26,
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 48,
  },
  // Fade the button while the order is being sent.
  buyButtonBusy: {
    opacity: 0.6,
  },
  // White "Buy" text inside the button
  buyButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  // ----- Portfolio box -----

  // White box that holds the portfolio values
  portfolioCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
  },
  // "Your portfolio" heading
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#171D22',
  },
  // Row with "AAPL shares held" on the left and the number on the right
  holdingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  // Number of shares held, e.g. "0"
  shareCount: {
    fontSize: 17,
    fontWeight: '500',
    color: '#171D22',
  },
  // Row with "Holdings value" and the amount, with a thin line above it
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#E8EBEE',
    paddingTop: 12,
    marginTop: 12,
  },
  // Large holdings amount, e.g. "$0.00"
  holdingsValue: {
    fontSize: 25,
    fontWeight: '600',
    color: '#171D22',
  },
  // Small note under the holdings value
  portfolioNote: {
    fontSize: 11,
    color: '#69737E',
    marginTop: 12,
  },

  // ----- Stock box more -----

  // Row with "Order total" on the left and the amount on the right, line above
  orderTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#E8EBEE',
  },
  // Order total amount, e.g. "$0.00"
  totalText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#171D22',
    fontVariant: ['tabular-nums'],
  },
  // Row with text on the left and right, e.g. "AAPL" and the "USD" badge
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  // Small "USD" badge with a border
  currency: {
    fontSize: 11,
    color: '#69737E',
    borderWidth: 1,
    borderColor: '#E8EBEE',
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 4,
  },
  // Red message shown when a purchase fails
  error: {
    backgroundColor: '#FFF0ED',
    color: '#A82D22',
    borderRadius: 10,
    padding: 12,
    marginTop: 14,
    fontSize: 13,
    lineHeight: 19,
  },
  // Green confirmation for a completed purchase.
  success: {
    backgroundColor: '#E8F5EE',
    color: '#087B51',
    borderRadius: 10,
    padding: 12,
    marginTop: 14,
    fontSize: 13,
    lineHeight: 19,
  },

  // ----- Bottom of the screen -----

  // "No real money is used." note at the bottom
  footer: {
    textAlign: 'center',
    fontSize: 12,
    color: '#69737E',
    marginTop: 8,
    marginBottom: 12,
  },
  // ----- Earned from steps box -----
  // White box that shows how today's steps turned into credits
  earnedCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
  },
  // Small green tag with the earning rate, e.g. "100 steps = 1 credit"
  ratePill: {
    fontSize: 11,
    color: '#087B51',
    backgroundColor: '#E8F5EE',
    borderRadius: 6,
    overflow: 'hidden',
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  // Large green amount earned, e.g. "+0 credits"
  earned: {
    fontSize: 16,
    fontWeight: '600',
    color: '#087B51',
    marginTop: 10,
  },
  // The calculation or status line under the amount
  math: {
    flexShrink: 1,
    fontSize: 13,
    color: '#171D22',
    marginTop: 4,
  },
  // Grey track of the daily limit bar
  limitBar: {
    height: 6,
    backgroundColor: '#E8EBEE',
    borderRadius: 3,
    overflow: 'hidden',
    marginTop: 12,
    marginBottom: 4,
  },
  // Green part of the bar: how much of today's limit is earned
  limitFill: {
    height: 6,
    backgroundColor: '#087B51',
  },

});