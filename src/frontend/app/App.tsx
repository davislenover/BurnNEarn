// import { StatusBar } from 'expo-status-bar';
// import { StyleSheet, Text, View } from 'react-native';
// import { useTodaySteps } from "./services/health/useTodaySteps";

// export default function App() {
//   const { steps } = useTodaySteps();

//   return (
//     <View style={styles.container}>
//       <Text>Today's steps: {steps ?? '—'}</Text>
//       <StatusBar style="auto" />
//     </View>
//   );
// }

// const styles = StyleSheet.create({
//   container: {
//     flex: 1,
//     backgroundColor: '#fff',
//     alignItems: 'center',
//     justifyContent: 'center',
//   },
// });

import { StatusBar } from 'expo-status-bar';
import DemoScreen from './screens/dashboard/DemoScreen';

// Root component: the app opens directly on the demo screen.
export default function App() {
  return (
    <>
      <DemoScreen />
      {/* Phone top bar (time, battery) */}
      <StatusBar style="auto" />
    </>
  );
}