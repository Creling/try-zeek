import React from 'react';
import { render } from 'react-dom';
import App from './App';

import thunkMiddleware from 'redux-thunk';
import createLogger from 'redux-logger';
import { createStore, applyMiddleware } from 'redux';
import { Provider } from 'react-redux';

import { tbhistory } from './tbhistory';
import { handleLocationChange } from './actions';

import tryBroApp from './reducers';

import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap/dist/css/bootstrap-theme.css';


const loggerMiddleware = createLogger();
const createStoreWithMiddleware = applyMiddleware(
  thunkMiddleware, // lets us dispatch() functions
  loggerMiddleware // neat middleware that logs actions
)(createStore);

const store = createStoreWithMiddleware(tryBroApp);

handleLocationChange(store.dispatch, tbhistory.location, true)
tbhistory.listen(function (location) {
    if(location.action !== 'PUSH' && location.action !== 'REPLACE')
        handleLocationChange(store.dispatch, location, false)
})

let rootElement = document.getElementById('root');
render(
  <Provider store={store}>
    <App />
  </Provider>,
  rootElement
);

