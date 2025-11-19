/** @format */

import React from "react"
import styled from "styled-components"
import GlobalStyle from "./styles/GlobalStyle"

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
`

const Title = styled.h1`
  font-size: 3rem;
  margin-bottom: 1rem;
  text-align: center;
`

const Subtitle = styled.p`
  font-size: 1.5rem;
  margin-bottom: 2rem;
  opacity: 0.9;
`

const Card = styled.div`
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
  border: 1px solid rgba(255, 255, 255, 0.18);
`

const TechList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`

const TechItem = styled.li`
  padding: 0.5rem 0;
  font-size: 1.2rem;

  &:before {
    content: "✓ ";
    color: #4ade80;
    font-weight: bold;
    margin-right: 0.5rem;
  }
`

function App() {
  return (
    <>
      <GlobalStyle />
      <Container>
        <Card>
          <Title>🚀 Electron + React</Title>
          <Subtitle>TypeScript & Styled Components</Subtitle>
          <TechList>
            <TechItem>React 18</TechItem>
            <TechItem>TypeScript</TechItem>
            <TechItem>Electron</TechItem>
            <TechItem>Styled Components</TechItem>
          </TechList>
        </Card>
      </Container>
    </>
  )
}

export default App
