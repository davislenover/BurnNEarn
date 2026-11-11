import { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

// Sample share price stored in cents: 12023 = $120.23
const sharePrice = 12023;

// Convert cents into a readable amount with two decimal places
function formatMoney(cents: number) {
  return (cents / 100).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function DemoScreen() {
  // Starting balance in cents: 100000 = $1,000
  const [balance, setBalance] = useState(100000);

  // Start with no shares
  const [sharesHeld, setSharesHeld] = useState(0);

  // Store the quantity entered in the input
  const [quantity, setQuantity] = useState('0');

  // Store a message when a purchase cannot proceed
  const [error, setError] = useState('');

  // Check that the quantity contains digits and is a positive whole number
  const shareCount = Number(quantity);
  const validQuantity =
    /^\d+$/.test(quantity) &&
    Number.isSafeInteger(shareCount) &&
    shareCount > 0;

  // Calculate the total in cents when the quantity is valid
  const orderTotal = validQuantity ? shareCount * sharePrice : 0;

  // Calculate the value of the shares held, excluding cash
  const holdingsValue = sharesHeld * sharePrice;

  // Check the order before changing the balance or shares
  function buyShares() {
    if (!validQuantity) {
      setError('Enter a positive whole number of shares.');
      return;
    }

    if (!Number.isSafeInteger(orderTotal)) {
      setError('The quantity is too large.');
      return;
    }

    if (orderTotal > balance) {
      setError('Not enough balance for this purchase.');
      return;
    }

    // Complete the simulated purchase
    setBalance(balance - orderTotal);
    setSharesHeld(sharesHeld + shareCount);
    setError('');
  }

  // Clear the previous error when the quantity changes
  function changeQuantity(value: string) {
    setQuantity(value);
    setError('');
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>FitFolio</Text>

      <View style={styles.summary}>
        {/* Steps box sample value */}
        <View style={styles.card}>
          <Text style={styles.label}>Today's steps</Text>
          <Text style={styles.number}>6,840</Text>
          <Text style={styles.caption}>steps today</Text>
        </View>

        {/* Balance updates after a purchase */}
        <View style={styles.card}>
          <Text style={styles.label}>Balance</Text>
          <Text style={styles.number} numberOfLines={1} adjustsFontSizeToFit>
            ${formatMoney(balance)}
          </Text>
          <Text style={styles.caption}>virtual credits</Text>
        </View>
      </View>

      {/* Stock price and purchase controls */}
      <View style={styles.stockCard}>
        <View style={styles.row}>
          <View>
            <Text style={styles.symbol}>AAPL</Text>
            <Text style={styles.caption}>Apple Inc. Sample price</Text>
          </View>
          <Text style={styles.currency}>USD</Text>
        </View>
        <Text style={styles.price}>${formatMoney(sharePrice)}</Text>

        <View style={styles.row}>
          <Text style={styles.label}>Quantity</Text>
        </View>

        <View style={styles.orderRow}>
          <TextInput
            style={styles.input}
            value={quantity}
            onChangeText={changeQuantity}
            keyboardType="number-pad"
            placeholder="1"
            placeholderTextColor="#69737E"
            accessibilityLabel="Number of shares to buy" />

          {/* Run the existing purchase checks when Buy is pressed */}
          <TouchableOpacity
            style={styles.buyButton}
            onPress={buyShares}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel="Buy AAPL shares">
            <Text style={styles.buyButtonText}>Buy</Text>
          </TouchableOpacity>
        </View>

        {/* Total cost for the entered quantity */}
        <View style={styles.orderTotal}>
          <Text style={styles.caption}>Order total</Text>
          <Text style={styles.totalText}>
            {validQuantity ? `$${formatMoney(orderTotal)}` : '—'}
          </Text>
        </View>

        {/* Show a message only when a purchase fails */}
        {error !== '' && (
          <Text style={styles.error} accessibilityRole="alert">
            {error}
          </Text>
        )}
      </View>

      {/* Portfolio updates after a purchase */}
      <View style={styles.portfolioCard}>
        <View style={styles.row}>
          <Text style={styles.sectionTitle}>Your portfolio</Text>
        </View>

        <View style={styles.holdingRow}>
          <Text style={styles.label}>AAPL shares held</Text>
          <Text style={styles.shareCount}>{sharesHeld}</Text>
        </View>

        <View style={styles.valueRow}>
          <Text style={styles.label}>Holdings value</Text>
          <Text style={styles.holdingsValue}>${formatMoney(holdingsValue)}</Text>
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
  // Screen spacing and background
  screen: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 80,
    paddingBottom: 40,
    gap: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '600',
    color: '#171D22',
  },

  // Two equal boxes beside each other
  summary: {
    flexDirection: 'row',
    gap: 12,
  },
  card: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
  },

  // Text shared by the steps and balance boxes
  label: {
    fontSize: 14,
    color: '#69737E',
  },
  number: {
    fontSize: 30,
    fontWeight: '600',
    color: '#171D22',
    marginTop: 16,
    marginBottom: 6,
  },
  caption: {
    fontSize: 12,
    color: '#69737E',
  },
  // Stock box and purchase controls
  stockCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
  },
  symbol: {
    fontSize: 17,
    fontWeight: '600',
    color: '#171D22',
    marginBottom: 5,
  },
  price: {
    fontSize: 36,
    fontWeight: '600',
    color: '#171D22',
    marginTop: 14,
    marginBottom: 24,
  },
  orderRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
  input: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderColor: '#D9DEE3',
    borderRadius: 11,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 18,
    color: '#171D22',
  },
  buyButton: {
    backgroundColor: '#087B51',
    borderRadius: 11,
    paddingHorizontal: 26,
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 48,
  },
  buyButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Portfolio box and its values
  portfolioCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#171D22',
  },
  holdingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 22,
  },
  shareCount: {
    fontSize: 17,
    fontWeight: '500',
    color: '#171D22',
  },
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#E8EBEE',
    paddingTop: 16,
    marginTop: 16,
  },
  holdingsValue: {
    fontSize: 25,
    fontWeight: '600',
    color: '#171D22',
  },
  portfolioNote: {
    fontSize: 11,
    color: '#69737E',
    marginTop: 12,
  },
  // Order total below the quantity input
  orderTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 16,
  },
  totalText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#171D22',
    fontVariant: ['tabular-nums'],
  },
  // Shared layout for labels on the same row
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  currency: {
    fontSize: 11,
    color: '#69737E',
    borderWidth: 1,
    borderColor: '#E8EBEE',
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 4,
  },

  // Purchase error message
  error: {
    backgroundColor: '#FFF0ED',
    color: '#A82D22',
    borderRadius: 10,
    padding: 12,
    marginTop: 14,
    fontSize: 13,
    lineHeight: 19,
  },
  footer: {
    textAlign: 'center',
    fontSize: 12,
    color: '#69737E',
    marginTop: 4,
    marginBottom: 16,
  },
});