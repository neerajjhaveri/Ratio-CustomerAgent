import Container from 'react-bootstrap/Container';

function HomePage() {
  return (
    <Container
      fluid
      className="d-flex flex-column align-items-center justify-content-center text-center"
      style={{ minHeight: '100%', padding: '0.5rem' }}
    >
      <h1 className="fw-bold mb-2" style={{ fontSize: '2.00rem', color: '#2c3e50' }}>
        Welcome to Ratio AI Workbench
      </h1>
      <br />
      <img
        src="./ratiobackground1.svg"
        alt="RATIO AI"
        className="d-block mx-auto mb-2"
        style={{ maxWidth: '45vw', maxHeight: '35vh', width: '45%', height: 'auto' }}
      />
      <br />
      {/* <h2 className="fw-normal" style={{ fontSize: '1.35rem', color: '#4a5568' }}>
        Welcome to Ratio AI Workbench
      </h2> */}
    </Container>
  );
}

export default HomePage;
