import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

export default function DemoScreen() {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>FitFolio</Text>

      <View style={styles.summary}>
        {/* Steps box — sample value */}
        <View style={styles.card}>
          <Text style={styles.label}>Today's steps</Text>
          <Text style={styles.number}>6,840</Text>
          <Text style={styles.caption}>steps today</Text>
        </View>

        {/* Balance box sample value */}
        <View style={styles.card}>
          <Text style={styles.label}>Balance</Text>
          <Text style={styles.number} numberOfLines={1} adjustsFontSizeToFit>$1,000
          </Text>
          <Text style={styles.caption}>virtual credits</Text>
        </View>
      </View>

      {/* Stock box — sample price */}
      <View style={styles.stockCard}>
        <Text style={styles.symbol}>AAPL</Text>
        <Text style={styles.caption}>Apple Inc. · Sample price per share</Text>
        <Text style={styles.price}>$230.23</Text>

        <Text style={styles.label}>Quantity</Text>

        <View style={styles.orderRow}>
          <TextInput
            style={styles.input}
            defaultValue="1"
            keyboardType="number-pad"
            accessibilityLabel="Number of shares to buy" />

          {/* Enable buy when purchase logic is added */}
          <TouchableOpacity style={styles.buyButton} disabled accessibilityRole="button" accessibilityState={{ disabled: true }}>
            <Text style={styles.buyButtonText}>Buy</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Portfolio box — sample values until purchases are connected */}
      <View style={styles.portfolioCard}>
        <Text style={styles.sectionTitle}>Your portfolio</Text>

        <View style={styles.holdingRow}>
          <Text style={styles.label}>AAPL shares held</Text>
          <Text style={styles.shareCount}>0</Text>
        </View>

        <View style={styles.valueRow}>
          <Text style={styles.label}>Holdings value</Text>
          <Text style={styles.holdingsValue}>$0.00</Text>
        </View>

        <Text style={styles.portfolioNote}>
          Shares x current price. Excludes cash.
        </Text>
      </View>
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
    opacity: 0.5,
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
});