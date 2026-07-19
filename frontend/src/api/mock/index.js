import MockAdapter from 'axios-mock-adapter';
import apiClient from '../client';
import authMock from './authMock';
import learningMock from './learningMock';
import quizMock from './quizMock';
import profileMock from './profileMock';
import teachingMock from './teachingMock';
import adminMock from './adminMock';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';

let mock = null;

if (useMock) {
  // This sets the mock adapter on the default instance
  // Set a 500ms delay to simulate network latency
  mock = new MockAdapter(apiClient, { delayResponse: 500 });

  // Register mocks
  authMock(mock);
  learningMock(mock);
  quizMock(mock);
  profileMock(mock);
  teachingMock(mock);
  adminMock(mock);

  console.log('[Mock API] Interceptor enabled.');
} else {
  console.log('[Mock API] Interceptor disabled. Using real API endpoints.');
}

export default mock;
export const isMockEnabled = useMock;
