from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler
import torch
from datetime import datetime

class SignalDataset(Dataset):
    def __init__(self, path, interval=21600, windows_size=100, test=False, fitbit=False, user_id=None):
        self.signal_df = pd.read_csv(path)
        if fitbit:
          self.signal_df=self.signal_df[self.signal_df.columns[:3]]
          self.signal_df = self.signal_df[self.signal_df['Id'] == user_id][self.signal_df.columns[-2:]]
          self.signal_df[self.signal_df.columns[-2]] = pd.to_datetime(self.signal_df[self.signal_df.columns[-2]])
          self.signal_df.columns = ['timestamp', 'value']
          self.signal_df['timestamp'] = list(map(lambda x: datetime.timestamp(x), self.signal_df['timestamp']))
          percentage=round(len(self.signal_df)/100*40) 
          self.signal_df = self.signal_df.head(percentage)  
          # test=user.iloc[percentage:len(user),:]

        self.interval = interval
        self.windows_size = windows_size
        self.test = test
        self.X, self.index = self.time_segments_aggregate(self.signal_df, interval=self.interval, time_column='timestamp')
        imp = SimpleImputer()
        self.X = imp.fit_transform(self.X)
        scaler = MinMaxScaler(feature_range=(-1, 1))
        self.X = scaler.fit_transform(self.X)
        self.X, self.y, self.X_index, self.y_index = self.rolling_window_sequences(self.X, self.index, 
                                                          window_size=self.windows_size, 
                                                          target_size=1, 
                                                          step_size=1,
                                                          target_column=0)


    def time_segments_aggregate(self, X, interval, time_column, method=['mean']):
        """Aggregate values over given time span.
        Args:
            X (ndarray or pandas.DataFrame):
                N-dimensional sequence of values.
            interval (int):
                Integer denoting time span to compute aggregation of.
            time_column (int):
                Column of X that contains time values.
            method (str or list):
                Optional. String describing aggregation method or list of strings describing multiple
                aggregation methods. If not given, `mean` is used.
        Returns:
            ndarray, ndarray:
                * Sequence of aggregated values, one column for each aggregation method.
                * Sequence of index values (first index of each aggregated segment).
        """
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X)

        X = X.sort_values(time_column).set_index(time_column)

        if isinstance(method, str):
            method = [method]

        start_ts = X.index.values[0]
        max_ts = X.index.values[-1]

        values = list()
        index = list()
        while start_ts <= max_ts:
            end_ts = start_ts + interval
            subset = X.loc[start_ts:end_ts - 1]
            aggregated = [
                getattr(subset, agg)(skipna=True).values
                for agg in method
            ]
            values.append(np.concatenate(aggregated))
            index.append(start_ts)
            start_ts = end_ts

        return np.asarray(values), np.asarray(index)



    def rolling_window_sequences(self, X, index, window_size, target_size, step_size, target_column,
                                offset=0, drop=None, drop_windows=False):
        """Create rolling window sequences out of time series data.
        The function creates an array of input sequences and an array of target sequences by rolling
        over the input sequence with a specified window.
        Optionally, certain values can be dropped from the sequences.
        Args:
            X (ndarray):
                N-dimensional sequence to iterate over.
            index (ndarray):
                Array containing the index values of X.
            window_size (int):
                Length of the input sequences.
            target_size (int):
                Length of the target sequences.
            step_size (int):
                Indicating the number of steps to move the window forward each round.
            target_column (int):
                Indicating which column of X is the target.
            offset (int):
                Indicating the number of steps between the input and the target sequence.
            drop (ndarray or None or str or float or bool):
                Optional. Array of boolean values indicating which values of X are invalid, or value
                indicating which value should be dropped. If not given, `None` is used.
            drop_windows (bool):
                Optional. Indicates whether the dropping functionality should be enabled. If not
                given, `False` is used.
        Returns:
            ndarray, ndarray, ndarray, ndarray:
                * input sequences.
                * target sequences.
                * first index value of each input sequence.
                * first index value of each target sequence.
        """
        out_X = list()
        out_y = list()
        X_index = list()
        y_index = list()
        target = X[:, target_column]

        if drop_windows:
            if hasattr(drop, '__len__') and (not isinstance(drop, str)):
                if len(drop) != len(X):
                    raise Exception('Arrays `drop` and `X` must be of the same length.')
            else:
                if isinstance(drop, float) and np.isnan(drop):
                    drop = np.isnan(X)
                else:
                    drop = X == drop

        start = 0
        max_start = len(X) - window_size - target_size - offset + 1
        while start < max_start:
            end = start + window_size

            if drop_windows:
                drop_window = drop[start:end + target_size]
                to_drop = np.where(drop_window)[0]
                if to_drop.size:
                    start += to_drop[-1] + 1
                    continue

            out_X.append(X[start:end])
            out_y.append(target[end + offset:end + offset + target_size])
            X_index.append(index[start])
            y_index.append(index[end + offset])
            start = start + step_size

        return np.asarray(out_X), np.asarray(out_y), np.asarray(X_index), np.asarray(y_index)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        row = self.X[idx]
        x = torch.from_numpy(row)
        if self.test: 
          return x, self.index, self.y, self.y_index, self.X_index
        return x

        # return {'value':x, 'anomaly':row['anomaly']}


