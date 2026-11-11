import { StyleSheet, Text, View } from 'react-native';

export default function DemoScreen() {
  return (
    /*Screen container with the title at the top*/
    <View style={styles.screen}>
      <Text style={styles.title}>FitFolio</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,                    // Fill the screen
    backgroundColor: '#F3F4F6', // Light grey background
    paddingHorizontal: 20,     // Space on both sides
    paddingTop: 80,             // Space above the title
  },

  title: {
    fontSize: 28,
    fontWeight: '600',
    color: '#171D22',
  },
});